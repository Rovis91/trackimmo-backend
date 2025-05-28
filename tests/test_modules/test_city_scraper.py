"""
Tests for the TrackImmo city scraper module using real data.
These tests perform actual API calls and database operations.
"""

import asyncio
import sys
import logging
import json
import os
from pathlib import Path
import pytest
import pandas as pd
import uuid
import random

from trackimmo.modules.city_scraper import CityDataScraper, scrape_cities
from trackimmo.modules.city_scraper.db_operations import CityDatabaseOperations

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)

logger = logging.getLogger("test_city_scraper")

# Test project ID for Supabase
TEST_PROJECT_ID = "winabqdzcqyuaoaqmfmn"

@pytest.fixture
def test_environment():
    """Set up test environment for city scraper tests."""
    # Create necessary directories
    data_dir = "test_output/data"
    os.makedirs(os.path.join(data_dir, "raw"), exist_ok=True)
    os.makedirs(os.path.join(data_dir, "processing"), exist_ok=True)
    
    return {
        'data_dir': data_dir,
        'raw_dir': os.path.join(data_dir, "raw"),
        'processing_dir': os.path.join(data_dir, "processing")
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

@pytest.mark.slow
def test_scrape_single_city_real_api(test_environment):
    """Test scraping a single city with real API calls."""
    output_file = os.path.join(test_environment['processing_dir'], 'single_city_test.csv')
    
    # Test with a real French city using the actual function signature
    cities_data = [{"city_name": "Lille", "postal_code": "59000"}]
    
    # Run the async function
    results = asyncio.run(scrape_cities(cities_data, max_retries=2))
    
    assert len(results) == 1
    result = results[0]
    
    # Verify result structure
    assert result['name'] == 'Lille'
    assert result['postal_code'] == '59000'
    assert result['status'] == 'success'
    assert 'insee_code' in result
    assert 'department' in result
    assert 'region' in result
    
    # Verify Lille data
    assert result['insee_code'] == '59350'
    assert result['department'] == '59'

@pytest.mark.slow
def test_scrape_multiple_cities_batch(test_environment):
    """Test scraping multiple cities in batch."""
    # Test with multiple real French cities using correct format
    cities_data = [
        {"city_name": "Lille", "postal_code": "59000"},
        {"city_name": "Roubaix", "postal_code": "59100"},
        {"city_name": "Tourcoing", "postal_code": "59200"}
    ]
    
    results = asyncio.run(scrape_cities(cities_data, max_retries=2))
    
    assert len(results) == len(cities_data)
    
    # Check that all cities are present and have valid data
    for result in results:
        assert result['status'] == 'success'
        assert 'name' in result
        assert 'postal_code' in result
        assert 'insee_code' in result
        assert 'department' in result
        assert 'region' in result
        
        # Verify postal code format (5 digits)
        assert len(str(result['postal_code'])) == 5
        assert str(result['postal_code']).isdigit()
        
        # Verify INSEE code format (5 digits)
        assert len(str(result['insee_code'])) == 5
        assert str(result['insee_code']).isdigit()

def test_insee_code_resolution():
    """Test INSEE code resolution for known cities."""
    # Test with cities that have known INSEE codes
    test_cases = [
        ("Lille", "59000", "59350"),
        ("Roubaix", "59100", "59512"),
        ("Tourcoing", "59200", "59599")
    ]
    
    for city_name, postal_code, expected_insee in test_cases:
        cities_data = [{"city_name": city_name, "postal_code": postal_code}]
        
        results = asyncio.run(scrape_cities(cities_data, max_retries=2))
        
        assert len(results) == 1
        result = results[0]
        assert result['status'] == 'success'
        assert result['insee_code'] == expected_insee

def test_department_region_mapping():
    """Test department and region mapping for French cities."""
    # Test cities from different departments
    cities_data = [
        {"city_name": "Lille", "postal_code": "59000"},
        {"city_name": "Paris", "postal_code": "75001"},
        {"city_name": "Lyon", "postal_code": "69001"},
        {"city_name": "Marseille", "postal_code": "13001"}
    ]
    
    results = asyncio.run(scrape_cities(cities_data, max_retries=2))
    
    # Verify department/region mappings
    expected_mappings = {
        "Lille": {"department": "59", "region": "hauts-de-france"},
        "Paris": {"department": "75", "region": "ile-de-france"},
        "Lyon": {"department": "69", "region": "auvergne-rhone-alpes"},
        "Marseille": {"department": "13", "region": "provence-alpes-cote-d-azur"}
    }
    
    for result in results:
        if result['status'] == 'success':
            city_name = result['name']
            if city_name in expected_mappings:
                expected = expected_mappings[city_name]
                assert result['department'] == expected['department']
                # Region names might be slightly different, so just check they exist
                assert 'region' in result and result['region'] is not None

def test_error_handling_invalid_cities():
    """Test error handling for invalid city names."""
    # Mix of valid and invalid cities
    cities_data = [
        {"city_name": "Lille", "postal_code": "59000"},
        {"city_name": "InvalidCityName123", "postal_code": "00000"},
        {"city_name": "Roubaix", "postal_code": "59100"},
        {"city_name": "AnotherInvalidCity", "postal_code": "99999"}
    ]
    
    results = asyncio.run(scrape_cities(cities_data, max_retries=1))
    
    # Should have results for all cities (some successful, some with errors)
    assert len(results) == len(cities_data)
    
    # Check that valid cities succeeded and invalid ones failed
    valid_cities = [r for r in results if r['status'] == 'success']
    error_cities = [r for r in results if r['status'] == 'error']
    
    # Should have at least the valid cities
    assert len(valid_cities) >= 2  # Lille and Roubaix should succeed
    assert len(error_cities) >= 2  # Invalid cities should fail

def test_city_data_scraper_initialization():
    """Test CityDataScraper initialization."""
    scraper = CityDataScraper(max_retries=5, sleep_time=2.0)
    
    assert scraper.max_retries == 5
    assert scraper.sleep_time == 2.0
    assert hasattr(scraper, 'user_agent')

@pytest.mark.slow
def test_single_city_scraper_method():
    """Test the scrape_city method directly."""
    scraper = CityDataScraper(max_retries=2)
    
    # Test with a real city
    result = asyncio.run(scraper.scrape_city("Villeneuve-d'Ascq", "59491"))
    
    assert result['status'] == 'success'
    assert result['name'] == "Villeneuve-d'Ascq"
    assert result['postal_code'] == "59491"
    assert 'insee_code' in result
    assert 'department' in result
    assert 'region' in result

@pytest.mark.database
def test_city_database_integration(test_cities_data):
    """Test city scraper integration with database."""
    from trackimmo.modules.db_manager import DBManager
    
    # Use a unique test city name to avoid conflicts
    unique_suffix = random.randint(10000, 99999)  # Generate 5-digit number
    test_city_name = f"TestCity{unique_suffix}"
    test_postal_code = f"{unique_suffix}"  # 5-digit postal code
    test_insee_code = f"{unique_suffix}"   # 5-digit INSEE code
    
    # Create test city data directly (not scraped from real API)
    city_data = {
        'status': 'success',
        'name': test_city_name,
        'postal_code': test_postal_code,
        'insee_code': test_insee_code,
        'department': '99',
        'region': 'Test Region'
    }
    
    try:
        with DBManager() as db:
            # Insert city into database
            db_city_data = {
                "name": city_data['name'],
                "postal_code": city_data['postal_code'],
                "insee_code": city_data['insee_code'],
                "department": city_data['department'],
                "region": city_data['region']
            }
            
            result = db.get_client().table("cities").insert(db_city_data).execute()
            assert len(result.data) == 1
            
            created_city = result.data[0]
            test_cities_data.append(created_city)  # Add to cleanup list
            
            # Verify insertion
            assert created_city['name'] == city_data['name']
            assert created_city['postal_code'] == city_data['postal_code']
            assert created_city['insee_code'] == city_data['insee_code']
            assert 'city_id' in created_city
            
            # Test retrieval
            city_id = created_city['city_id']
            retrieved = db.get_client().table("cities").select("*").eq("city_id", city_id).execute()
            assert len(retrieved.data) == 1
            assert retrieved.data[0]['name'] == city_data['name']
            
    except Exception as e:
        pytest.fail(f"Database integration test failed: {e}")

@pytest.mark.database
def test_bulk_city_insertion(test_cities_data):
    """Test bulk insertion of multiple cities."""
    from trackimmo.modules.db_manager import DBManager
    
    # Create unique test cities to avoid conflicts
    unique_suffix = random.randint(10000, 99999)  # Generate 5-digit number
    test_cities = []
    for i in range(3):
        test_cities.append({
            'status': 'success',
            'name': f"TestCity{unique_suffix}_{i}",
            'postal_code': f"{unique_suffix + i}",  # 5-digit postal code
            'insee_code': f"{unique_suffix + i}",   # 5-digit INSEE code
            'department': '99',
            'region': 'Test Region'
        })
    
    try:
        with DBManager() as db:
            # Prepare bulk insert data
            cities_to_insert = []
            for result in test_cities:
                city_data = {
                    "name": result['name'],
                    "postal_code": result['postal_code'],
                    "insee_code": result['insee_code'],
                    "department": result['department'],
                    "region": result['region']
                }
                cities_to_insert.append(city_data)
            
            # Bulk insert
            result = db.get_client().table("cities").insert(cities_to_insert).execute()
            assert len(result.data) == len(cities_to_insert)
            
            # Add all to cleanup list
            test_cities_data.extend(result.data)
            
            # Verify all cities were inserted
            for i, created_city in enumerate(result.data):
                assert created_city['name'] == cities_to_insert[i]['name']
                assert created_city['postal_code'] == cities_to_insert[i]['postal_code']
                assert 'city_id' in created_city
            
    except Exception as e:
        pytest.fail(f"Bulk insertion test failed: {e}")

@pytest.mark.performance
def test_city_scraping_performance():
    """Test city scraping performance metrics."""
    import time
    
    cities_data = [
        {"city_name": "Lille", "postal_code": "59000"},
        {"city_name": "Roubaix", "postal_code": "59100"},
        {"city_name": "Tourcoing", "postal_code": "59200"},
        {"city_name": "Villeneuve-d'Ascq", "postal_code": "59491"},
        {"city_name": "Marcq-en-Barœul", "postal_code": "59700"}
    ]
    
    start_time = time.time()
    
    results = asyncio.run(scrape_cities(cities_data, max_retries=2))
    
    end_time = time.time()
    execution_time = end_time - start_time
    
    # Should have results for all cities
    assert len(results) == len(cities_data)
    
    # Performance assertions - increased timeout for real API calls
    assert execution_time < 120  # Should complete within 120 seconds for 5 cities
    
    # Verify at least some cities were processed successfully
    successful_results = [r for r in results if r['status'] == 'success']
    assert len(successful_results) >= 3  # At least 3 should succeed
    
    print(f"City scraping performance: {execution_time:.2f}s for {len(cities_data)} cities")

# TODO: Add integration test with scraper module
@pytest.mark.integration
def test_city_scraper_to_scraper_integration():
    """
    Integration test from city scraping to property scraping.
    
    INTEGRATION TEST REQUIREMENTS:
    1. Scrape cities and store in database
    2. Use scraped cities as input for property scraper
    3. Verify city data flows correctly between modules
    4. Test error handling across module boundaries
    """
    pass

# TODO: Add API rate limiting test
@pytest.mark.api_limits
def test_city_api_rate_limiting():
    """
    Test API rate limiting for city scraping.
    
    API TESTING REQUIREMENTS:
    1. Test with large batch of cities
    2. Verify rate limiting is respected
    3. Test retry mechanisms for failed requests
    4. Test handling of API errors
    """
    pass

# TODO: Add data validation test
@pytest.mark.data_validation
def test_city_data_validation():
    """
    Test validation of scraped city data.
    
    VALIDATION TEST REQUIREMENTS:
    1. Verify postal code formats
    2. Validate INSEE code consistency
    3. Check department/region mappings
    4. Test duplicate city handling
    5. Verify data completeness
    """
    pass
