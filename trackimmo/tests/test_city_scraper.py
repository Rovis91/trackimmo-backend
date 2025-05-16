#!/usr/bin/env python3
"""
Test script for the city data scraper.
"""

import asyncio
import sys
import logging
import json
import os
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from trackimmo.modules.city_scraper.city_scraper import CityDataScraper
from trackimmo.modules.city_scraper.db_operations import CityDatabaseOperations

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)

logger = logging.getLogger("test_city_scraper")

async def test_single_city():
    """Test scraping data for a single city."""
    # City to test
    city_name = "Lille"
    postal_code = "59000"
    
    logger.info(f"Testing city scraper for {city_name} ({postal_code})")
    
    # Initialize scraper
    scraper = CityDataScraper()
    
    # Scrape city data
    city_data = await scraper.scrape_city(city_name, postal_code)
    
    # Print results
    logger.info("Scraping results:")
    logger.info(f"INSEE Code: {city_data.get('insee_code')}")
    logger.info(f"Department: {city_data.get('department')}")
    logger.info(f"Region: {city_data.get('region')}")
    logger.info(f"House Price Avg: {city_data.get('house_price_avg')}")
    logger.info(f"Apartment Price Avg: {city_data.get('apartment_price_avg')}")
    
    # Save results to JSON file
    os.makedirs("test_output", exist_ok=True)
    output_file = "test_output/city_scraper_test.json"
    
    with open(output_file, "w") as f:
        json.dump(city_data, f, indent=2)
    
    logger.info(f"Results saved to {output_file}")
    
    # Update database (optional)
    update_db = input("Update database with this data? (y/n): ").strip().lower()
    
    if update_db == "y":
        logger.info("Updating database...")
        db_ops = CityDatabaseOperations()
        result = db_ops.update_city(city_data)
        
        logger.info(f"Database update result: {result.get('status')}")
        if result.get("error_message"):
            logger.error(f"Error: {result.get('error_message')}")
    else:
        logger.info("Skipping database update")
    
    return city_data

if __name__ == "__main__":
    # Run test
    result = asyncio.run(test_single_city())
    
    # Exit with status code
    if result.get("status") == "success":
        sys.exit(0)
    else:
        sys.exit(1)