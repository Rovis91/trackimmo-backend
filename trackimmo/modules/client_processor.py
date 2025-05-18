"""
Client processing module for TrackImmo.
"""
import random
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional
import uuid

from trackimmo.utils.logger import get_logger
from trackimmo.modules.db_manager import DBManager
from trackimmo.modules.city_scraper import CityDataScraper, scrape_cities
from trackimmo.modules.scraper import ImmoDataScraper
from trackimmo.utils.email_sender import send_client_notification

logger = get_logger(__name__)

async def process_client_data(client_id: str) -> Dict[str, Any]:
    """
    Process a client's data and assign new properties.
    Logs a job in processing_jobs for every attempt.
    
    Args:
        client_id: The client's UUID
        
    Returns:
        Dict with results of processing
    """
    logger.info(f"Processing client {client_id}")
    now = datetime.now()
    job_id = str(uuid.uuid4())
    try:
        with DBManager() as db:
            # Insert job as 'processing'
            db.get_client().table("processing_jobs").insert({
                "job_id": job_id,
                "client_id": client_id,
                "status": "processing",
                "attempt_count": 1,
                "last_attempt": now.isoformat(),
                "next_attempt": (now + timedelta(hours=1)).isoformat(),
                "error_message": None,
                "created_at": now.isoformat(),
                "updated_at": now.isoformat()
            }).execute()
        # 1. Get client data
        client = get_client_by_id(client_id)
        if not client or client["status"] != "active":
            raise ValueError(f"Client {client_id} not found or inactive")
        
        # 2. Process cities (enrich if needed)
        await update_client_cities(client)
        
        # 3. Scrape and extract properties
        await scrape_properties_for_client(client)
        
        # 4. Assign properties to client
        assign_count = client.get("addresses_per_report", 10)  # Default 10 if not set
        new_addresses = assign_properties_to_client(client, assign_count)
        
        # 5. Send notification
        if new_addresses:
            send_client_notification(client, new_addresses)
        
        # 6. Update client's last_updated field
        update_client_last_updated(client_id)
        
        logger.info(f"Processed client {client_id}: {len(new_addresses)} properties assigned")
        
        # Mark job as completed
        with DBManager() as db:
            db.get_client().table("processing_jobs").update({
                "status": "completed",
                "updated_at": datetime.now().isoformat()
            }).eq("job_id", job_id).execute()
        return {
            "success": True,
            "properties_assigned": len(new_addresses),
            "client_id": client_id
        }
    except Exception as e:
        logger.error(f"Error processing client {client_id}: {str(e)}")
        # Mark job as failed
        with DBManager() as db:
            db.get_client().table("processing_jobs").update({
                "status": "failed",
                "error_message": str(e),
                "updated_at": datetime.now().isoformat()
            }).eq("job_id", job_id).execute()
        raise

def get_client_by_id(client_id: str) -> Optional[Dict[str, Any]]:
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

async def scrape_properties_for_client(client: Dict[str, Any]):
    """
    Scrape properties for a client's cities.
    
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
        
        # Use your existing scraper for each city
        for city in response.data:
            try:
                logger.info(f"Scraping properties for city {city['name']} ({city['city_id']})")
                # Initialize scraper
                scraper = ImmoDataScraper()
                # Set date range for past 3 months
                today = datetime.now()
                start_date = (today - timedelta(days=90)).strftime("%m/%Y")
                end_date = today.strftime("%m/%Y")
                # Scrape properties (async)
                result_file = await scraper.scrape_city_async(
                    city_name=city["name"],
                    postal_code=city["postal_code"],
                    property_types=client["property_type_preferences"],
                    start_date=start_date,
                    end_date=end_date
                )
                logger.info(f"Scraped properties for {city['name']} saved to {result_file}")
            except Exception as e:
                logger.error(f"Error scraping properties for city {city['city_id']}: {str(e)}")

def assign_properties_to_client(client: Dict[str, Any], count: int = 10) -> List[Dict[str, Any]]:
    """
    Assign properties to a client.
    
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
    
    with DBManager() as db:
        # Get previously assigned properties
        assigned_response = db.get_client().table("client_addresses").select("address_id").eq("client_id", client_id).execute()
        assigned_address_ids = [item["address_id"] for item in assigned_response.data]
        
        # Get eligible properties (not already assigned to this client)
        query = db.get_client().table("addresses").select("*")
        
        # Filter by city
        if city_ids:
            query = query.in_("city_id", city_ids)
            
        # Filter by property type
        if property_types:
            query = query.in_("property_type", property_types)
            
        properties_response = query.execute()
        
        # Filter out already assigned properties
        eligible_properties = [p for p in properties_response.data if p["address_id"] not in assigned_address_ids]
        
        # Sort by sale date (oldest first)
        eligible_properties.sort(key=lambda p: p.get("sale_date", ""), reverse=False)
        
        # Add some randomization while still prioritizing oldest
        # Group by month
        months = {}
        for prop in eligible_properties:
            sale_date = prop.get("sale_date", "")
            month_key = sale_date[:7] if sale_date else "unknown"  # YYYY-MM format
            if month_key not in months:
                months[month_key] = []
            months[month_key].append(prop)
        
        # Randomize within each month and create a new list
        prioritized_properties = []
        for month_key in sorted(months.keys()):  # Sort by month (oldest first)
            randomized_month = random.sample(months[month_key], len(months[month_key]))
            prioritized_properties.extend(randomized_month)
        
        # Select properties to assign
        properties_to_assign = prioritized_properties[:min(count, len(prioritized_properties))]
        
        # Check if we have enough properties
        if len(properties_to_assign) < count:
            logger.warning(f"Only {len(properties_to_assign)} properties available for client {client_id}, requested {count}")
        
        # Assign properties
        assigned_properties = []
        now = datetime.now().isoformat()
        
        for prop in properties_to_assign:
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
            except Exception as e:
                logger.error(f"Error assigning property {prop['address_id']} to client {client_id}: {str(e)}")
        
        logger.info(f"Assigned {len(assigned_properties)} properties to client {client_id}")
        return assigned_properties

def update_client_last_updated(client_id: str):
    """Update the client's last_updated timestamp."""
    now = datetime.now().isoformat()
    
    with DBManager() as db:
        db.get_client().table("clients").update({
            "last_updated": now,
            "updated_at": now
        }).eq("client_id", client_id).execute()
        
    logger.info(f"Updated last_updated timestamp for client {client_id}")