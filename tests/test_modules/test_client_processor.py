"""
Tests for the client processor module.
"""
import pytest
import uuid
from unittest.mock import patch, MagicMock
from datetime import datetime

from trackimmo.modules.client_processor import (
    process_client_data,
    get_client_by_id,
    update_client_cities,
    assign_properties_to_client
)

# Use real client ID from the test database
TEST_CLIENT_ID = "e86f4960-f848-4236-b45c-0759b95db5a3"
INACTIVE_CLIENT_ID = "e86f4960-f848-4236-b45c-0759b95db5a4"  # Similar but inactive

@pytest.fixture
def mock_client():
    """Create a mock client for testing."""
    return {
        "client_id": TEST_CLIENT_ID,
        "first_name": "Test",
        "last_name": "User",
        "email": "test@example.com",
        "status": "active",
        "chosen_cities": ["c1d2e3f4-a1b2-c3d4-e5f6-a1b2c3d4e5f6", "c1d2e3f4-a1b2-c3d4-e5f6-a1b2c3d4e5f7"],
        "property_type_preferences": ["house", "apartment"],
        "addresses_per_report": 5
    }

@pytest.fixture
def mock_properties():
    """Create mock properties for testing."""
    return [
        {
            "address_id": str(uuid.uuid4()),
            "address_raw": "123 Test St",
            "city_id": "c1d2e3f4-a1b2-c3d4-e5f6-a1b2c3d4e5f6",
            "sale_date": "2023-01-15",
            "property_type": "house",
            "price": 250000
        },
        {
            "address_id": str(uuid.uuid4()),
            "address_raw": "456 Sample Ave",
            "city_id": "c1d2e3f4-a1b2-c3d4-e5f6-a1b2c3d4e5f7",
            "sale_date": "2023-02-20",
            "property_type": "apartment",
            "price": 180000
        }
    ]

@patch('trackimmo.modules.client_processor.DBManager')
@pytest.mark.asyncio
async def test_process_client_data(mock_db_manager, mock_client, mock_properties):
    """Test the process_client_data function."""
    # Configure the database mock
    mock_db = MagicMock()
    mock_db_manager.return_value.__enter__.return_value = mock_db
    mock_client_table = MagicMock()
    mock_db.get_client.return_value.table.return_value = mock_client_table
    
    # Mock responses for database operations
    mock_response = MagicMock()
    mock_response.data = [mock_client]
    mock_client_table.select.return_value.eq.return_value.execute.return_value = mock_response
    
    # Mock the required functions
    with patch('trackimmo.modules.client_processor.update_client_cities') as mock_update_cities, \
         patch('trackimmo.modules.client_processor.scrape_properties_for_client') as mock_scrape, \
         patch('trackimmo.modules.client_processor.assign_properties_to_client') as mock_assign, \
         patch('trackimmo.modules.client_processor.send_client_notification') as mock_send, \
         patch('trackimmo.modules.client_processor.update_client_last_updated') as mock_update:
        
        # Set up return values
        mock_update_cities.return_value = None
        mock_scrape.return_value = None
        mock_assign.return_value = mock_properties
        mock_send.return_value = None
        mock_update.return_value = None
        
        # Run the function
        result = await process_client_data(TEST_CLIENT_ID)
        
        # Verify the result
        assert result["success"] is True
        assert "properties_assigned" in result
        assert result["client_id"] == TEST_CLIENT_ID

@patch('trackimmo.modules.client_processor.DBManager')
@pytest.mark.asyncio
async def test_process_client_data_inactive_client(mock_db_manager):
    """Test processing an inactive client."""
    # Configure the database mock
    mock_db = MagicMock()
    mock_db_manager.return_value.__enter__.return_value = mock_db
    mock_client_table = MagicMock()
    mock_db.get_client.return_value.table.return_value = mock_client_table
    
    # Mock an inactive client
    inactive_client = {
        "client_id": INACTIVE_CLIENT_ID,
        "status": "inactive"
    }
    
    # Mock responses for database operations
    mock_response = MagicMock()
    mock_response.data = [inactive_client]
    mock_client_table.select.return_value.eq.return_value.execute.return_value = mock_response
    
    # Verify that an error is raised
    with pytest.raises(ValueError) as exc_info:
        await process_client_data(INACTIVE_CLIENT_ID)
    
    # Check the error message
    assert "inactive" in str(exc_info.value).lower()

@pytest.mark.asyncio
@patch('trackimmo.modules.client_processor.DBManager')
async def test_assign_properties_to_client(mock_db_manager, mock_client, mock_properties):
    """Test the assign_properties_to_client function."""
    # Configure mock DB
    mock_db = MagicMock()
    mock_table = MagicMock()
    mock_query = MagicMock()
    
    # Configure response for client_addresses query
    mock_assigned_response = MagicMock()
    mock_assigned_response.data = []
    
    # Configure response for addresses query
    mock_properties_response = MagicMock()
    mock_properties_response.data = mock_properties
    
    # Set up the mock chain
    mock_db_manager.return_value.__enter__.return_value = mock_db
    mock_db.get_client.return_value.table.return_value = mock_table
    mock_table.select.return_value = mock_query
    mock_query.eq.return_value.execute.return_value = mock_assigned_response
    mock_query.in_.return_value = mock_query
    mock_query.execute.return_value = mock_properties_response
    
    # Run the function
    result = await assign_properties_to_client(mock_client, 3)
    
    # Verify the results
    assert len(result) == 2  # Should return both properties since only 2 available 