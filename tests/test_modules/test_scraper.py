"""
Tests for the TrackImmo scraper module using real data.
These tests perform actual scraping operations and database interactions.
"""
import os
import csv
import pytest
import pandas as pd
from pathlib import Path
from datetime import datetime, timedelta

from trackimmo.modules.scraper import ImmoDataScraper
from trackimmo.modules.scraper.geo_divider import GeoDivider
from trackimmo.modules.scraper.url_generator import UrlGenerator

# Test project ID for Supabase
TEST_PROJECT_ID = "winabqdzcqyuaoaqmfmn"

@pytest.fixture
def test_environment():
    """Set up test environment for scraper tests."""
    # Create necessary directories
    data_dir = "test_output/data"
    os.makedirs(os.path.join(data_dir, "scraped"), exist_ok=True)
    os.makedirs(os.path.join(data_dir, "raw"), exist_ok=True)
    
    return {
        'data_dir': data_dir,
        'scraped_dir': os.path.join(data_dir, "scraped"),
        'raw_dir': os.path.join(data_dir, "raw")
    }

@pytest.fixture
def test_cities_data():
    """Test cities data to be inserted and cleaned up."""
    return []

@pytest.fixture(autouse=True)
def cleanup_test_data(test_cities_data):
    """Automatically cleanup test data after each test."""
    yield
    
    # Cleanup any test cities that were created
    if test_cities_data:
        try:
            from trackimmo.modules.db_manager import DBManager
            with DBManager() as db:
                for city_data in test_cities_data:
                    if 'city_id' in city_data:
                        # Delete test city
                        db.get_client().table("cities").delete().eq("city_id", city_data['city_id']).execute()
        except Exception as e:
            print(f"Warning: Could not cleanup test city data: {e}")

def test_geographic_division_real_coordinates():
    """Test geographic division with real Lille coordinates."""
    # Test with GeoDivider which is the actual class
    geo_divider = GeoDivider()
    
    # Test with a small city (Lille)
    rectangles = geo_divider.divide_city_area("Lille", "59000", overlap_percent=10)
    
    assert len(rectangles) > 0
    assert all('center_lat' in rect for rect in rectangles)
    assert all('center_lon' in rect for rect in rectangles)
    assert all('min_lat' in rect for rect in rectangles)
    assert all('max_lat' in rect for rect in rectangles)
    assert all('min_lon' in rect for rect in rectangles)
    assert all('max_lon' in rect for rect in rectangles)
    
    # Verify coordinates are reasonable for Lille area
    for rect in rectangles:
        assert 50.5 < rect['center_lat'] < 50.7  # Lille latitude range
        assert 2.9 < rect['center_lon'] < 3.2    # Lille longitude range

def test_url_generator_real_endpoints():
    """Test URL generation with actual ImmoData endpoints."""
    url_generator = UrlGenerator()
    
    # Create sample rectangles (based on Lille coordinates)
    rectangles = [{
        "center_lat": 50.6292,
        "center_lon": 3.0573,
        "min_lat": 50.6,
        "min_lon": 3.0,
        "max_lat": 50.65,
        "max_lon": 3.1,
        "zoom": 12
    }]
    
    urls = url_generator.generate_urls(
        rectangles=rectangles,
        property_types=["house", "apartment"],
        start_date="01/2023",
        end_date="02/2023"
    )
    
    assert len(urls) > 0
    
    for url_data in urls:
        assert 'url' in url_data
        assert 'rectangle' in url_data
        assert 'property_type' in url_data
        assert 'period' in url_data
        assert url_data['url'].startswith('https://www.immo-data.fr')

def test_scraper_initialization(test_environment):
    """Test scraper initialization with real configuration."""
    scraper = ImmoDataScraper(output_dir=test_environment['scraped_dir'])
    
    # Verify scraper initialization
    assert scraper is not None
    # Normalize path separators for comparison
    expected_path = os.path.normpath(test_environment['scraped_dir'])
    actual_path = os.path.normpath(str(scraper.output_dir))
    assert actual_path == expected_path
    assert hasattr(scraper, 'geo_divider')
    assert hasattr(scraper, 'url_generator')

@pytest.mark.slow
def test_small_scale_scraping(test_environment):
    """Test actual scraping with small area (Tourcoing/Roubaix)."""
    scraper = ImmoDataScraper(output_dir=test_environment['scraped_dir'])
    
    # Use a small city and short time period for testing
    result_file = scraper.scrape_city(
        city_name="Tourcoing",  # Smaller city near Lille
        postal_code="59200",
        property_types=["house"],  # Only houses to limit results
        start_date="01/2024",      # Recent single month
        end_date="01/2024"
    )
    
    # Verify file was created
    assert os.path.exists(result_file)
    
    # Verify CSV structure
    df = pd.read_csv(result_file)
    expected_columns = ['address', 'city', 'price', 'surface', 'rooms', 'sale_date', 'property_type', 'property_url']
    
    for col in expected_columns:
        assert col in df.columns
    
    # Verify data types and content
    if len(df) > 0:
        # Handle case sensitivity - check if city name matches (case insensitive)
        city_name = df['city'].iloc[0].lower()
        assert city_name == "tourcoing"
        assert df['property_type'].iloc[0] == "house"
        assert pd.to_numeric(df['price'], errors='coerce').notna().any()
        assert pd.to_numeric(df['surface'], errors='coerce').notna().any()

def test_csv_export_format(test_environment):
    """Test CSV export format and data validation."""
    scraper = ImmoDataScraper(output_dir=test_environment['scraped_dir'])
    
    # Create sample data
    sample_properties = [
        {
            "address": "123 Test Street", 
            "city": "TestCity",
            "price": 300000,
            "surface": 120.5,
            "rooms": 4,
            "sale_date": "15/01/2023",
            "property_type": "house",
            "property_url": "https://example.com/property1"
        }
    ]
    
    # Test the CSV export functionality
    output_file = os.path.join(scraper.output_dir, "test_export.csv")
    scraper._export_to_csv(sample_properties, Path(output_file))
    
    # Verify file exists and has correct format
    assert os.path.exists(output_file)
    
    df = pd.read_csv(output_file)
    assert len(df) == 1
    assert df.iloc[0]['address'] == "123 Test Street"
    assert df.iloc[0]['price'] == 300000
    assert df.iloc[0]['surface'] == 120.5

def test_error_handling_invalid_bbox():
    """Test error handling for invalid bounding box."""
    # Test with GeoDivider which handles the geographic operations
    geo_divider = GeoDivider()
    
    # Test with invalid city name
    try:
        rectangles = geo_divider.divide_city_area("InvalidCityName123", "00000")
        # Should handle invalid city gracefully (might return empty list or raise exception)
        assert isinstance(rectangles, list)
    except Exception as e:
        # If it raises an exception, it should be a clear error message
        assert "city" in str(e).lower() or "not found" in str(e).lower()

@pytest.mark.database
def test_scraper_database_integration(test_cities_data):
    """Test scraper integration with database for city tracking."""
    from trackimmo.modules.db_manager import DBManager
    
    # Create test city
    test_city = {
        "name": "Scraper Test City",
        "postal_code": "77777",
        "insee_code": "77777",
        "department": "77",
        "region": "Test Region"
    }
    
    try:
        with DBManager() as db:
            # Insert test city
            result = db.get_client().table("cities").insert(test_city).execute()
            created_city = result.data[0]
            test_cities_data.append(created_city)  # Add to cleanup list
            
            city_id = created_city['city_id']
            
            # Update last_scraped timestamp
            update_result = db.get_client().table("cities").update({
                "last_scraped": datetime.now().isoformat()
            }).eq("city_id", city_id).execute()
            
            assert len(update_result.data) == 1
            
            # Verify update
            updated_city = db.get_client().table("cities").select("*").eq("city_id", city_id).execute()
            assert updated_city.data[0]['last_scraped'] is not None
            
    except Exception as e:
        pytest.fail(f"Database integration test failed: {e}")

@pytest.mark.performance
def test_scraping_performance_metrics():
    """Test scraping performance and resource usage."""
    import time
    import psutil
    import os
    
    # Small test configuration
    scraper = ImmoDataScraper(output_dir="test_output/data/scraped")
    
    # Monitor performance
    process = psutil.Process(os.getpid())
    start_memory = process.memory_info().rss / 1024 / 1024  # MB
    start_time = time.time()
    
    # Test with very limited scope
    try:
        result_file = scraper.scrape_city(
            city_name="Hem",  # Very small city
            postal_code="59510",
            property_types=["apartment"],
            start_date="01/2024",
            end_date="01/2024"
        )
        success = os.path.exists(result_file)
    except Exception:
        success = True  # Even if scraping fails, we can measure performance
    
    end_time = time.time()
    end_memory = process.memory_info().rss / 1024 / 1024  # MB
    
    # Performance assertions
    execution_time = end_time - start_time
    memory_usage = end_memory - start_memory
    
    # Should complete within reasonable time (increased timeout for real scraping)
    assert execution_time < 300  # Should complete within 5 minutes
    
    # Memory usage should be reasonable
    assert memory_usage < 200  # Should not use more than 200MB additional memory
    
    print(f"Scraping performance: {execution_time:.2f}s, {memory_usage:.2f}MB")

# TODO: Add integration test with enrichment pipeline
@pytest.mark.integration
def test_scraper_to_enrichment_integration():
    """
    Integration test from scraping to enrichment pipeline.
    
    INTEGRATION TEST REQUIREMENTS:
    1. Scrape small dataset from real source
    2. Pass scraped data to enrichment pipeline
    3. Verify data flows correctly between modules
    4. Test error handling across module boundaries
    5. Verify final output quality
    """
    pass

# TODO: Add rate limiting and politeness test
@pytest.mark.rate_limiting
def test_scraping_rate_limits():
    """
    Test scraping rate limiting and server politeness.
    
    RATE LIMITING TEST REQUIREMENTS:
    1. Test delay between requests is respected
    2. Test handling of HTTP 429 (Too Many Requests)
    3. Test exponential backoff on errors
    4. Verify User-Agent rotation if implemented
    5. Test concurrent scraping limits
    """
    pass

# TODO: Add data quality validation test
@pytest.mark.data_quality
def test_scraped_data_quality():
    """
    Test quality and consistency of scraped data.
    
    DATA QUALITY TEST REQUIREMENTS:
    1. Validate address formats
    2. Check price ranges are reasonable
    3. Verify date formats and ranges
    4. Test property type consistency
    5. Check for duplicate detection
    """
    pass 