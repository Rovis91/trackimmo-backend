"""
Database operations for city data.
"""

import logging
from typing import Dict, Any, Optional, List
from pprint import pformat

from trackimmo.modules.db_manager import DBManager
from trackimmo.utils.logger import get_logger

logger = get_logger(__name__)

class CityDatabaseOperations:
    """Database operations for cities."""
    
    def __init__(self):
        """Initialize the database operations."""
        self.db_manager = None
    
    def update_cities(self, cities_data: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Update multiple cities in the database.
        
        Args:
            cities_data: List of city data dicts
        
        Returns:
            List of results
        """
        results = []
        
        try:
            self.db_manager = DBManager()
            logger.info(f"Updating {len(cities_data)} cities in the database")
            
            for city_data in cities_data:
                try:
                    result = self.update_city(city_data)
                    results.append(result)
                except Exception as e:
                    logger.error(f"Error updating city {city_data.get('name')}: {str(e)}")
                    city_data["status"] = "error"
                    city_data["error_message"] = str(e)
                    results.append(city_data)
            
            return results
            
        except Exception as e:
            logger.error(f"Error connecting to database: {str(e)}")
            # Return original data with error status
            for city_data in cities_data:
                city_data["status"] = "error"
                city_data["error_message"] = f"Database connection error: {str(e)}"
                results.append(city_data)
            return results
        finally:
            if self.db_manager:
                # No need to close the connection explicitly with DBManager
                pass
    
    def update_city(self, city_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Update a city in the database.
        
        Args:
            city_data: City data dict
        
        Returns:
            Updated city data
        """
        if not self.db_manager:
            self.db_manager = DBManager()
        
        try:
            with self.db_manager as db:
                supabase_client = db.get_client()
                
                # Check if city already exists by INSEE code
                insee_code = city_data.get("insee_code")
                
                if not insee_code:
                    logger.warning(f"Missing INSEE code for city {city_data.get('name')}")
                    city_data["status"] = "error"
                    city_data["error_message"] = "Missing INSEE code"
                    return city_data
                
                # Prepare data for upsert
                upsert_data = {
                    "name": city_data.get("name"),
                    "postal_code": city_data.get("postal_code"),
                    "insee_code": insee_code,
                    "department": city_data.get("department"),
                    "region": city_data.get("region"),
                    "last_scraped": "now()",
                    "updated_at": "now()"
                }
                
                # Add price data if available
                if city_data.get("house_price_avg"):
                    upsert_data["house_price_avg"] = city_data["house_price_avg"]
                
                if city_data.get("apartment_price_avg"):
                    upsert_data["apartment_price_avg"] = city_data["apartment_price_avg"]
                
                # Perform upsert operation
                logger.info(f"Upserting city data for {city_data.get('name')} ({insee_code})")
                logger.debug(f"Upsert data: {pformat(upsert_data)}")
                
                response = supabase_client.table("cities").upsert(upsert_data).execute()
                
                if response.data and len(response.data) > 0:
                    logger.info(f"Successfully updated city {city_data.get('name')}")
                    # Update city_data with city_id from response
                    city_data["city_id"] = response.data[0].get("city_id")
                    city_data["status"] = "success"
                else:
                    logger.warning(f"No response data from upsert operation for {city_data.get('name')}")
                
                return city_data
                
        except Exception as e:
            logger.error(f"Error updating city {city_data.get('name')}: {str(e)}")
            city_data["status"] = "error"
            city_data["error_message"] = str(e)
            return city_data