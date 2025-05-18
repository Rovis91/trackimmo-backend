"""
Tests for the TrackImmo scraper module.
"""
import os
import csv
import json
import pytest
import pandas as pd
import asyncio
from unittest.mock import patch, MagicMock, AsyncMock
from pathlib import Path

from trackimmo.modules.scraper.scraper import ImmoDataScraper

@pytest.fixture
def scraper():
    """Create a scraper instance for testing."""
    test_output_dir = "test_output"
    os.makedirs(test_output_dir, exist_ok=True)
    return ImmoDataScraper(output_dir=test_output_dir)

def test_scraper_initialization(scraper):
    """Test that the scraper can be initialized correctly."""
    assert str(scraper.output_dir) == "test_output"
    # The scraper object is properly created
    assert isinstance(scraper, ImmoDataScraper)

def test_scraper_city_method(scraper):
    """Test that the scraper has city scraping methods."""
    assert hasattr(scraper, 'scrape_city')
    assert callable(scraper.scrape_city)
    
    # Also verify async version exists
    assert hasattr(scraper, 'scrape_city_async')
    assert callable(scraper.scrape_city_async)

@pytest.mark.asyncio
async def test_scrape_city_async():
    """Test the async scraper method with proper mocks."""
    test_output_dir = "test_output"
    os.makedirs(test_output_dir, exist_ok=True)
    
    # Create a test CSV file path
    test_csv_path = os.path.join(test_output_dir, "test_properties.csv")
    
    # Create sample property data
    sample_properties = [
        {
            "address": "123 Test Street", 
            "city": "Lille",
            "price": 300000,
            "surface": 120,
            "rooms": 4,
            "sale_date": "2023-01-15",
            "property_type": "house"
        },
        {
            "address": "456 Sample Avenue", 
            "city": "Lille",
            "price": 250000,
            "surface": 80,
            "rooms": 3,
            "sale_date": "2023-02-20",
            "property_type": "apartment"
        }
    ]
    
    # Create the scraper instance
    scraper = ImmoDataScraper(output_dir=test_output_dir)
    
    # Create mock to replace browser functionality
    async def mock_scrape_city_async_impl(*args, **kwargs):
        """Mock implementation that returns sample properties."""
        return sample_properties
    
    # Apply the patch to bypass browser operations
    with patch.object(scraper, '_scrape_city_async', new=AsyncMock(side_effect=mock_scrape_city_async_impl)):
        # Create mock for the geo_divider
        scraper.geo_divider = MagicMock()
        scraper.geo_divider.divide_city_area.return_value = [{"lat1": 50.6, "lon1": 3.0, "lat2": 50.7, "lon2": 3.1}]
        
        # Create mock for url_generator
        scraper.url_generator = MagicMock()
        scraper.url_generator.generate_urls.return_value = [{"url": "test_url", "rectangle": {}, "month": "01/2023"}]
        
        # Call the async method
        result_file = await scraper.scrape_city_async(
            city_name="Lille",
            postal_code="59000",
            property_types=["house", "apartment"],
            start_date="01/2023",
            end_date="03/2023",
            output_file=test_csv_path
        )
        
        # Verify the result is a file path
        assert os.path.exists(result_file)
        
        # Verify the CSV file contains our sample data
        df = pd.read_csv(result_file)
        assert len(df) == 2
        assert "Lille" in df["city"].values
        assert 300000 in df["price"].values
        assert "house" in df["property_type"].values
        assert "apartment" in df["property_type"].values 