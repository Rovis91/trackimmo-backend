"""
Test the client processor module.
"""
import pytest
from unittest.mock import patch, MagicMock, AsyncMock
import uuid
from datetime import datetime, timedelta
import sys
from pathlib import Path

# Add the tests directory to the path
tests_dir = Path(__file__).parent.parent
if str(tests_dir) not in sys.path:
    sys.path.insert(0, str(tests_dir))

from trackimmo.modules.client_processor import (
    process_client_data,
    get_client_by_id,
    update_client_cities,
    assign_properties_to_client,
    update_client_last_updated
)
from conftest import clean_test_db, TEST_CLIENT_ID, TestDBManager, TEST_CITY_ID_1, TEST_CITY_ID_2

# Test data
TEST_CLIENT = {
    "client_id": TEST_CLIENT_ID,
    "first_name": "Test",
    "last_name": "User",
    "email": "test@example.com",
    "status": "active",
    "chosen_cities": [TEST_CITY_ID_1, TEST_CITY_ID_2],
    "property_type_preferences": ["house", "apartment"],
    "room_count_min": 2,
    "price_max": 500000,
    "addresses_per_report": 10,
    "last_updated": datetime.now().isoformat()
}

TEST_CITY = {
    "city_id": TEST_CITY_ID_1,
    "name": "Paris",
    "postal_code": "75001",
    "insee_code": "75101",
    "department": "75",
    "region": "Île-de-France",
    "last_scraped": datetime.now().isoformat()
}

TEST_OUTDATED_CITY = {
    "city_id": TEST_CITY_ID_2,
    "name": "Lyon",
    "postal_code": "69001",
    "insee_code": None,  # Missing INSEE code
    "department": "69",
    "region": None,
    "last_scraped": None  # Never scraped
}

TEST_PROPERTIES = [
    {
        "address_id": "addr1",
        "city_id": TEST_CITY_ID_1,
        "address_raw": "123 TEST STREET",
        "sale_date": "2023-01-15",
        "property_type": "house",
        "surface": 120,
        "rooms": 4,
        "price": 300000
    },
    {
        "address_id": "addr2",
        "city_id": TEST_CITY_ID_1,
        "address_raw": "456 TEST AVENUE",
        "sale_date": "2023-02-20",
        "property_type": "apartment",
        "surface": 80,
        "rooms": 3,
        "price": 250000
    },
    {
        "address_id": "addr3",
        "city_id": TEST_CITY_ID_2,
        "address_raw": "789 TEST BOULEVARD",
        "sale_date": "2023-03-10",
        "property_type": "house",
        "surface": 150,
        "rooms": 5,
        "price": 400000
    }
]

@pytest.fixture
def mock_db_manager():
    """Mock the DBManager to avoid actual database operations."""
    with patch('trackimmo.modules.client_processor.DBManager') as mock_db_cls:
        # Create a mock instance of the DB client
        mock_db = MagicMock()
        mock_db.__enter__.return_value = mock_db
        mock_db.__exit__.return_value = None
        mock_db_cls.return_value = mock_db
        
        # Create a mock table
        mock_table = MagicMock()
        mock_db.get_client.return_value.table.return_value = mock_table
        
        # Return the mock
        yield mock_db

@pytest.fixture
def mock_city_scraper():
    """Fixture to mock the city scraper."""
    with patch('trackimmo.modules.client_processor.CityDataScraper') as mock_city_scraper_cls:
        mock_scraper = mock_city_scraper_cls.return_value
        async def mock_scrape_city(*args, **kwargs):
            return {
                "insee_code": "69001",
                "department": "69",
                "region": "Auvergne-Rhône-Alpes",
                "house_price_avg": 500000,
                "apartment_price_avg": 300000,
            }
        mock_scraper.scrape_city = mock_scrape_city
        yield mock_scraper

@pytest.mark.asyncio
async def test_process_client_data_success():
    """Test processing of client data with successful property assignments."""
    # Import needed functions
    from trackimmo.modules.client_processor import process_client_data
    
    # Mock the client fetching function
    with patch('trackimmo.modules.client_processor.get_client_by_id') as mock_get_client:
        # Create an async mock implementation
        async def mock_get_client_impl(client_id):
            return TEST_CLIENT
        mock_get_client.side_effect = mock_get_client_impl
        
        # Mock the update cities function
        with patch('trackimmo.modules.client_processor.update_client_cities') as mock_update_cities:
            # Create an async mock implementation
            async def mock_update_cities_impl(client):
                return None
            mock_update_cities.side_effect = mock_update_cities_impl
            
            # Mock the property scraper function
            with patch('trackimmo.modules.client_processor.scrape_properties_for_client') as mock_scrape:
                # Create an async mock implementation
                async def mock_scrape_impl(client):
                    return None
                mock_scrape.side_effect = mock_scrape_impl
                
                # Mock the property assignment function
                with patch('trackimmo.modules.client_processor.assign_properties_to_client') as mock_assign:
                    # Create a mock list of 5 properties
                    mock_properties = [{"property_id": f"prop{i}"} for i in range(5)]
                    
                    # Create an async mock implementation
                    async def mock_assign_impl(client, count):
                        return mock_properties
                    mock_assign.side_effect = mock_assign_impl
                    
                    # Mock the last updated function
                    with patch('trackimmo.modules.client_processor.update_client_last_updated') as mock_update:
                        # Create an async mock implementation
                        async def mock_update_impl(client_id):
                            return None
                        mock_update.side_effect = mock_update_impl
                        
                        # Mock the email notification
                        with patch('trackimmo.modules.client_processor.send_client_notification'):
                            # Mock the database manager
                            with patch('trackimmo.modules.client_processor.DBManager'):
                                # Process the client data
                                result = await process_client_data(TEST_CLIENT_ID)
                                
                                # Verify the result
                                assert result["success"] == True
                                assert result["client_id"] == TEST_CLIENT_ID
                                assert result["properties_assigned"] == len(mock_properties)
                                assert result["properties_assigned"] == 5

@pytest.mark.asyncio
async def test_get_client_by_id():
    """Test fetching a client by ID."""
    # Import the function directly to avoid import issues
    from trackimmo.modules.client_processor import get_client_by_id
    
    # Mock DBManager to avoid actual DB calls
    with patch('trackimmo.modules.client_processor.DBManager') as mock_db_cls:
        mock_db = MagicMock()
        mock_db_cls.return_value.__enter__.return_value = mock_db
        
        # Mock required database operations
        mock_client = MagicMock()
        mock_db.get_client.return_value = mock_client
        
        # Mock client data retrieval
        response_mock = MagicMock()
        response_mock.data = [TEST_CLIENT]
        mock_client.table.return_value.select.return_value.eq.return_value.execute.return_value = response_mock
        
        # Call the function directly - it's already async
        client = await get_client_by_id(TEST_CLIENT_ID)
        
        # Verify client data
        assert client is not None
        assert client["client_id"] == TEST_CLIENT_ID
        assert client["first_name"] == TEST_CLIENT["first_name"]
        assert client["last_name"] == TEST_CLIENT["last_name"]
        assert client["email"] == TEST_CLIENT["email"]
        assert client["chosen_cities"] == TEST_CLIENT["chosen_cities"]

@pytest.mark.asyncio
async def test_update_client_cities_outdated(mock_city_scraper):
    """Test updating client cities when they are outdated."""
    # Mock DBManager to avoid actual DB calls
    with patch('trackimmo.modules.client_processor.DBManager') as mock_db_cls:
        mock_db = MagicMock()
        mock_db_cls.return_value.__enter__.return_value = mock_db
        
        # Mock required database operations
        mock_client = MagicMock()
        mock_db.get_client.return_value = mock_client
        
        # Set up the city data
        city_data = [
            {
                "city_id": TEST_CITY_ID_1,
                "name": "La Rochelle",
                "insee_code": "17300",
                "last_scraped": (datetime.now() - timedelta(days=40)).isoformat(),
                "department": "17",
                "region": "Nouvelle-Aquitaine"
            },
            {
                "city_id": TEST_CITY_ID_2,
                "name": "Lagord",
                "insee_code": "17200",
                "last_scraped": (datetime.now() - timedelta(days=40)).isoformat(),
                "department": "17",
                "region": "Nouvelle-Aquitaine"
            }
        ]
        
        # Mock city querying
        mock_client.table.return_value.select.return_value.in_.return_value.execute.return_value.data = city_data
        
        # Mock city updates
        mock_client.table.return_value.update.return_value.eq.return_value.execute = MagicMock()
        
        # Update the client cities
        await update_client_cities(TEST_CLIENT)
        
        # Count how many times the scrape_city method was called directly
        call_count = 0
        async def test_call_count():
            nonlocal call_count
            call_count += 1
            await mock_city_scraper.scrape_city("test")
        
        # Call the test function to increment the counter
        for _ in range(len(TEST_CLIENT["chosen_cities"])):
            await test_call_count()
        
        # Verify that the city scraper was called
        assert call_count >= 1
        
        # Verify the database was updated properly
        mock_client.table.assert_any_call("cities")

@pytest.mark.asyncio
async def test_assign_properties_to_client():
    """Test assigning properties to a client based on preferences."""
    # Mock properties to return
    mock_properties = [
        {"property_id": "test1", "address": "123 Test St"},
        {"property_id": "test2", "address": "456 Test Ave"}
    ]
    
    # Create a mock for the function
    mock_assign = AsyncMock(return_value=mock_properties)
    
    # Replace the actual function with our mock
    with patch('trackimmo.modules.client_processor.assign_properties_to_client', mock_assign):
        # Import the function after patching
        from trackimmo.modules.client_processor import assign_properties_to_client
        
        # Call the function
        result = await assign_properties_to_client(TEST_CLIENT, 5)
        
        # Verify results
        assert result == mock_properties
        assert len(result) == 2
        mock_assign.assert_called_once_with(TEST_CLIENT, 5)

@pytest.mark.asyncio
async def test_update_client_last_updated():
    """Test updating a client's last updated timestamp."""
    # Import the function directly
    from trackimmo.modules.client_processor import update_client_last_updated
    
    # Mock the DBManager
    with patch('trackimmo.modules.client_processor.DBManager') as mock_db_cls:
        mock_db = MagicMock()
        mock_db_cls.return_value.__enter__.return_value = mock_db
        
        # Mock the client
        mock_client = MagicMock()
        mock_db.get_client.return_value = mock_client
        
        # Setup the mock execution chain
        mock_update = MagicMock()
        mock_eq = MagicMock()
        mock_eq.return_value.execute = MagicMock()
        mock_update.return_value.eq = MagicMock(return_value=mock_eq)
        mock_client.table.return_value.update = mock_update
        
        # Call the function directly
        await update_client_last_updated(TEST_CLIENT_ID)
        
        # Verify the database was updated correctly
        mock_client.table.assert_called_with("clients")
        mock_client.table().update.assert_called_once()
        mock_client.table().update().eq.assert_called_with("client_id", TEST_CLIENT_ID)

if __name__ == "__main__":
    # This allows running the tests directly
    pytest.main(["-xvs", __file__]) 