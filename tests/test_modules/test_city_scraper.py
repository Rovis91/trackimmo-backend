"""
Test script for the city data scraper.
"""

import asyncio
import sys
import logging
import json
import os
from pathlib import Path
import pytest

from trackimmo.modules.city_scraper.city_scraper import CityDataScraper
from trackimmo.modules.city_scraper.db_operations import CityDatabaseOperations

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)

logger = logging.getLogger("test_city_scraper")

@pytest.mark.asyncio
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
    
    # Validate test results
    assert city_data.get('insee_code') is not None, "INSEE code should not be None"
    assert city_data.get('department') is not None, "Department should not be None"
    assert city_data.get('region') is not None, "Region should not be None"
    
    return city_data 