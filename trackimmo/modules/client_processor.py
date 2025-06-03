"""
Client processing module for TrackImmo.
"""
import random
import os
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional
import uuid
from pathlib import Path

from trackimmo.utils.logger import get_logger
from trackimmo.modules.db_manager import DBManager
from trackimmo.modules.city_scraper import CityDataScraper, scrape_cities
from trackimmo.modules.scraper import ImmoDataScraper
from trackimmo.modules.enrichment import EnrichmentOrchestrator
from trackimmo.utils.email_sender import send_client_notification

logger = get_logger(__name__)

async def process_client_data(client_id: str, skip_scraping: bool = False) -> Dict[str, Any]:
    """
    Process a client's data and assign new properties.
    
    Args:
        client_id: The client's UUID
        skip_scraping: If True, skip scraping and only run enrichment on existing data
        
    Returns:
        Dict with results of processing
    """
    logger.info(f"Processing client {client_id}, skip_scraping: {skip_scraping}")
    
    try:
        # 1. Get client data
        client = await get_client_by_id(client_id)
        if not client or client["status"] != "active":
            raise ValueError(f"Client {client_id} not found or inactive")
        
        # 2. Process cities (enrich if needed) - only if not skipping scraping
        if not skip_scraping:
            await update_client_cities(client)
        
        # 3. Scrape, enrich and insert properties (only if needed and not skipping)
        if skip_scraping:
            await enrich_existing_scraped_data_for_client(client)
        else:
            await scrape_and_enrich_properties_for_client(client)
        
        # 4. Assign properties to client
        assign_count = client.get("addresses_per_report", 10)  # Default 10 if not set
        new_addresses = await assign_properties_to_client(client, assign_count)
        
        # 5. Send notification if new addresses found
        if new_addresses:
            await send_client_notification(client, new_addresses)
        
        # 6. Update client's last_updated field
        await update_client_last_updated(client_id)
        
        logger.info(f"Processed client {client_id}: {len(new_addresses)} properties assigned")
        
        return {
            "success": True,
            "properties_assigned": len(new_addresses),
            "client_id": client_id,
            "message": f"Successfully assigned {len(new_addresses)} properties"
        }
    except Exception as e:
        logger.error(f"Error processing client {client_id}: {str(e)}")
        raise

async def get_client_by_id(client_id: str) -> Optional[Dict[str, Any]]:
    """Get a client by ID."""
    with DBManager() as db:
        response = db.get_client().table("clients").select("*").eq("client_id", client_id).execute()
        if response.data and len(response.data) > 0:
            return response.data[0]
        return None

async def update_client_cities(client: Dict[str, Any]):
    """
    Update the client's cities data if needed.
    
    Args:
        client: The client data
    """
    if not client.get("chosen_cities"):
        logger.warning(f"Client {client['client_id']} has no chosen cities")
        return
    
    with DBManager() as db:
        for city_id in client["chosen_cities"]:
            # Get city data
            response = db.get_client().table("cities").select("*").eq("city_id", city_id).execute()
            if not response.data or len(response.data) == 0:
                logger.warning(f"City {city_id} not found for client {client['client_id']}")
                continue
                
            city = response.data[0]
            
            # Check if city needs updating (older than 3 months or missing data)
            last_scraped = city.get("last_scraped")
            needs_update = False
            
            if not last_scraped:
                needs_update = True
            else:
                try:
                    last_scraped_date = datetime.fromisoformat(last_scraped.replace('Z', '+00:00'))
                    if (datetime.now() - last_scraped_date).days > 90:
                        needs_update = True
                except (ValueError, TypeError):
                    needs_update = True
            
            # If INSEE code is missing, needs update
            if not city.get("insee_code"):
                needs_update = True
                
            if needs_update:
                logger.info(f"Updating data for city {city['name']} ({city_id})")
                try:
                    scraper = CityDataScraper()
                    city_data = await scraper.scrape_city(city["name"], city["postal_code"])
                    
                    # Update city in database
                    db.get_client().table("cities").update({
                        "insee_code": city_data.get("insee_code"),
                        "department": city_data.get("department"),
                        "region": city_data.get("region"),
                        "house_price_avg": city_data.get("house_price_avg"),
                        "apartment_price_avg": city_data.get("apartment_price_avg"),
                        "last_scraped": datetime.now().isoformat(),
                        "updated_at": datetime.now().isoformat()
                    }).eq("city_id", city_id).execute()
                    
                except Exception as e:
                    logger.error(f"Error updating city {city_id}: {str(e)}")

async def scrape_and_enrich_properties_for_client(client: Dict[str, Any]):
    """
    Scrape properties for a client's cities, enrich them, and insert into database.
    
    Args:
        client: The client data
    """
    if not client.get("chosen_cities") or not client.get("property_type_preferences"):
        logger.warning(f"Client {client['client_id']} has no chosen cities or property types")
        return
    
    with DBManager() as db:
        # Get cities data
        city_ids = client["chosen_cities"]
        response = db.get_client().table("cities").select("*").in_("city_id", city_ids).execute()
        
        # Check if we have enough properties for each city
        for city in response.data:
            try:
                # Count existing properties for this city in the age range we need (6-8 years)
                min_date = (datetime.now() - timedelta(days=8*365)).strftime("%Y-%m-%d")
                max_date = (datetime.now() - timedelta(days=6*365)).strftime("%Y-%m-%d")
                
                count_response = db.get_client().table("addresses").select("address_id", count="exact") \
                    .eq("city_id", city["city_id"]) \
                    .gte("sale_date", min_date) \
                    .lte("sale_date", max_date) \
                    .in_("property_type", client["property_type_preferences"]) \
                    .execute()
                
                existing_count = count_response.count or 0
                logger.info(f"City {city['name']}: {existing_count} existing properties in 6-8 year range")
                
                # If we have less than 50 properties, scrape more
                if existing_count < 50:
                    logger.info(f"Scraping properties for city {city['name']} ({city['city_id']})")
                    
                    # Initialize scraper
                    scraper = ImmoDataScraper()
                    # Set date range for 6-8 years ago
                    start_date = (datetime.now() - timedelta(days=8*365)).strftime("%m/%Y")
                    end_date = (datetime.now() - timedelta(days=6*365)).strftime("%m/%Y")
                    
                    # Scrape properties (async)
                    result_file = await scraper.scrape_city_async(
                        city_name=city["name"],
                        postal_code=city["postal_code"],
                        property_types=client["property_type_preferences"],
                        start_date=start_date,
                        end_date=end_date
                    )
                    logger.info(f"Scraped properties for {city['name']} saved to {result_file}")
                    
                    # Now run the enrichment pipeline to process and insert the scraped data
                    await enrich_and_insert_properties(result_file, city)
                    
                else:
                    logger.info(f"Sufficient properties exist for {city['name']}, skipping scrape")
                    
            except Exception as e:
                logger.error(f"Error processing properties for city {city['city_id']}: {str(e)}")

async def enrich_existing_scraped_data_for_client(client: Dict[str, Any]):
    """
    Find existing scraped data and run enrichment on it for a client's cities.
    
    Args:
        client: The client data
    """
    if not client.get("chosen_cities") or not client.get("property_type_preferences"):
        logger.warning(f"Client {client['client_id']} has no chosen cities or property types")
        return
    
    # Look for scraped files in the data/scraped directory
    scraped_dir = Path("data/scraped")
    if not scraped_dir.exists():
        logger.warning("No scraped data directory found")
        return
    
    with DBManager() as db:
        # Get cities data
        city_ids = client["chosen_cities"]
        response = db.get_client().table("cities").select("*").in_("city_id", city_ids).execute()
        
        # Look for existing scraped files for each city
        for city in response.data:
            try:
                city_name = city["name"]
                postal_code = city["postal_code"]
                
                # Look for CSV files that match this city
                # File naming pattern is typically: CityName_PostalCode_*.csv
                city_files = []
                for csv_file in scraped_dir.glob("*.csv"):
                    filename = csv_file.name.lower()
                    city_name_clean = city_name.lower().replace(" ", "_").replace("-", "_")
                    
                    if (city_name_clean in filename or 
                        postal_code in filename or
                        city_name.lower() in filename):
                        city_files.append(csv_file)
                
                if not city_files:
                    logger.info(f"No scraped files found for city {city_name} ({postal_code})")
                    continue
                
                # Process each found file
                for csv_file in city_files:
                    logger.info(f"Found scraped file for {city_name}: {csv_file}")
                    
                    # Check file size to ensure it has data
                    if csv_file.stat().st_size < 1000:  # Less than 1KB likely empty
                        logger.warning(f"Scraped file {csv_file} appears to be empty, skipping")
                        continue
                    
                    # Run enrichment pipeline on this file
                    logger.info(f"Running enrichment on {csv_file}")
                    await enrich_and_insert_properties(str(csv_file), city)
                    
                if city_files:
                    logger.info(f"Processed {len(city_files)} scraped files for {city_name}")
                    
            except Exception as e:
                logger.error(f"Error processing existing scraped data for city {city['city_id']}: {str(e)}")

async def enrich_and_insert_properties(csv_file: str, city: Dict[str, Any]):
    """
    Run the enrichment pipeline on scraped properties and insert them into the database.
    
    Args:
        csv_file: Path to the CSV file with scraped properties
        city: City data dictionary
    """
    try:
        logger.info(f"Starting enrichment pipeline for {csv_file}")
        
        # Configure enrichment with city bounding box if available
        config = {
            'data_dir': str(Path(csv_file).parent.parent),  # Go up to data directory
            'original_bbox': {
                'min_lat': city.get('min_lat', 0),
                'max_lat': city.get('max_lat', 0),
                'min_lon': city.get('min_lon', 0),
                'max_lon': city.get('max_lon', 0)
            } if all(k in city for k in ['min_lat', 'max_lat', 'min_lon', 'max_lon']) else None
        }
        
        # Run enrichment pipeline asynchronously
        orchestrator = EnrichmentOrchestrator(config)
        success = await orchestrator.run_async(
            input_file=csv_file,
            start_stage=1,  # Start from normalization
            end_stage=7,    # End at database integration (changed from 6 to 7 to include DB integration)
            debug=False     # Don't keep intermediate files
        )
        
        if success:
            logger.info(f"Enrichment pipeline completed successfully for {city['name']}")
        else:
            logger.error(f"Enrichment pipeline failed for {city['name']}")
            
        # Clean up the original CSV file
        try:
            os.remove(csv_file)
            logger.info(f"Cleaned up scraped file: {csv_file}")
        except Exception as e:
            logger.warning(f"Could not remove scraped file {csv_file}: {str(e)}")
            
    except Exception as e:
        logger.error(f"Error in enrichment pipeline for {csv_file}: {str(e)}")
        raise

async def assign_properties_to_client(client: Dict[str, Any], count: int = 10) -> List[Dict[str, Any]]:
    """
    Assign properties to a client following business rules:
    - Properties sold 6-8 years ago
    - In client's chosen cities and property types
    - Not already assigned to this client
    - Semi-random selection favoring older properties
    
    Args:
        client: The client data
        count: Number of properties to assign
        
    Returns:
        List of assigned properties
    """
    client_id = client["client_id"]
    city_ids = client.get("chosen_cities", [])
    property_types = client.get("property_type_preferences", [])
    
    logger.info(f"Assigning {count} properties to client {client_id}")
    logger.info(f"Criteria: cities={len(city_ids)}, types={property_types}")
    
    if not city_ids or not property_types:
        logger.warning(f"Client {client_id} missing criteria: cities={len(city_ids)}, types={len(property_types)}")
        return []
    
    with DBManager() as db:
        # Get previously assigned properties
        assigned_response = db.get_client().table("client_addresses").select("address_id").eq("client_id", client_id).execute()
        assigned_address_ids = [item["address_id"] for item in assigned_response.data]
        logger.info(f"Client {client_id} already has {len(assigned_address_ids)} assigned properties")
        
        # Define age range: 6-8 years ago
        min_date = (datetime.now() - timedelta(days=8*365)).strftime("%Y-%m-%d")
        max_date = (datetime.now() - timedelta(days=6*365)).strftime("%Y-%m-%d")
        
        logger.info(f"Looking for properties sold between {min_date} and {max_date}")
        
        # Get eligible properties
        query = db.get_client().table("addresses").select("*") \
            .in_("city_id", city_ids) \
            .in_("property_type", property_types) \
            .gte("sale_date", min_date) \
            .lte("sale_date", max_date)
        
        # Exclude already assigned properties
        if assigned_address_ids:
            query = query.not_.in_("address_id", assigned_address_ids)
            
        properties_response = query.execute()
        eligible_properties = properties_response.data
        
        logger.info(f"Found {len(eligible_properties)} eligible properties")
        
        if not eligible_properties:
            logger.warning(f"No eligible properties found for client {client_id}")
            return []
        
        # Apply weighted random selection favoring older properties
        selected_properties = weighted_random_selection(eligible_properties, count)
        
        logger.info(f"Selected {len(selected_properties)} properties for assignment")
        
        # Assign properties
        assigned_properties = []
        now = datetime.now().isoformat()
        
        for prop in selected_properties:
            try:
                # Create client_address record
                client_address_id = str(uuid.uuid4())
                db.get_client().table("client_addresses").insert({
                    "client_id": client_id,
                    "address_id": prop["address_id"],
                    "client_address_id": client_address_id,
                    "send_date": now,
                    "status": "new",
                    "created_at": now,
                    "updated_at": now
                }).execute()
                
                assigned_properties.append(prop)
                logger.info(f"Assigned property {prop['address_id']} to client {client_id}")
                
            except Exception as e:
                logger.error(f"Error assigning property {prop['address_id']} to client {client_id}: {str(e)}")
        
        logger.info(f"Successfully assigned {len(assigned_properties)} properties to client {client_id}")
        return assigned_properties

def weighted_random_selection(properties: List[Dict[str, Any]], count: int) -> List[Dict[str, Any]]:
    """
    Select properties with weighted randomization favoring older properties.
    
    Args:
        properties: List of eligible properties
        count: Number of properties to select
        
    Returns:
        Selected properties
    """
    if len(properties) <= count:
        return properties
    
    # Sort by sale date (oldest first)
    sorted_properties = sorted(properties, key=lambda p: p.get("sale_date", ""), reverse=False)
    
    # Create weights: older properties get higher weights
    weights = []
    total_properties = len(sorted_properties)
    
    for i, prop in enumerate(sorted_properties):
        # Weight decreases linearly from oldest to newest
        # Oldest property gets weight = total_properties, newest gets weight = 1
        weight = total_properties - i
        weights.append(weight)
    
    # Perform weighted random selection
    selected_properties = []
    available_indices = list(range(len(sorted_properties)))
    available_weights = weights.copy()
    
    for _ in range(min(count, len(sorted_properties))):
        # Choose index based on weights
        chosen_idx = random.choices(available_indices, weights=available_weights, k=1)[0]
        
        # Add to selection
        actual_idx = available_indices[chosen_idx]
        selected_properties.append(sorted_properties[actual_idx])
        
        # Remove from available options
        available_indices.pop(chosen_idx)
        available_weights.pop(chosen_idx)
        
        if not available_indices:
            break
    
    logger.info(f"Weighted selection: chose {len(selected_properties)} from {total_properties} properties")
    return selected_properties

async def update_client_last_updated(client_id: str):
    """Update the client's last_updated timestamp."""
    with DBManager() as db:
        db.get_client().table("clients").update({
            "updated_at": datetime.now().isoformat()
        }).eq("client_id", client_id).execute()

# Keep existing utility functions
def filter_properties_by_preferences(properties: List[Dict[str, Any]], client_preferences: Dict[str, Any]) -> List[Dict[str, Any]]:
    """
    Filter properties based on client preferences.
    
    Args:
        properties: List of property data
        client_preferences: Client preferences including property_type_preferences and chosen_cities
        
    Returns:
        Filtered list of properties
    """
    filtered = []
    
    property_types = client_preferences.get('property_type_preferences', [])
    chosen_cities = client_preferences.get('chosen_cities', [])
    
    for prop in properties:
        # Filter by property type
        if property_types and prop.get('property_type') not in property_types:
            continue
            
        # Filter by city
        if chosen_cities and prop.get('city_id') not in chosen_cities:
            continue
            
        filtered.append(prop)
    
    return filtered

def deduplicate_properties(properties: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Remove duplicate properties based on address.
    
    Args:
        properties: List of property data
        
    Returns:
        Deduplicated list of properties
    """
    seen_addresses = {}
    deduplicated = []
    
    for prop in properties:
        address_key = prop.get('address_raw', '').lower().strip()
        city_key = prop.get('city_id', '')
        combined_key = f"{address_key}_{city_key}"
        
        if combined_key not in seen_addresses:
            seen_addresses[combined_key] = prop
            deduplicated.append(prop)
        else:
            # Keep the property with the more recent sale date or higher price
            existing = seen_addresses[combined_key]
            current_date = prop.get('sale_date', '')
            existing_date = existing.get('sale_date', '')
            
            # If current property has a more recent date, replace
            if current_date > existing_date:
                # Remove old property and add new one
                deduplicated = [p for p in deduplicated if p != existing]
                seen_addresses[combined_key] = prop
                deduplicated.append(prop)
            elif current_date == existing_date:
                # If same date, keep the one with higher price
                current_price = float(prop.get('price', 0))
                existing_price = float(existing.get('price', 0))
                if current_price > existing_price:
                    deduplicated = [p for p in deduplicated if p != existing]
                    seen_addresses[combined_key] = prop
                    deduplicated.append(prop)
    
    return deduplicated