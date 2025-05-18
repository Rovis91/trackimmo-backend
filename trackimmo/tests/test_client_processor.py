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

@pytest.fixture
def mock_client():
    """Create a mock client for testing."""
    return {
        "client_id": str(uuid.uuid4()),
        "first_name": "Test",
        "last_name": "User",
        "email": "test@example.com",
        "status": "active",
        "chosen_cities": [str(uuid.uuid4()), str(uuid.uuid4())],
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
            "city_id": str(uuid.uuid4()),
            "sale_date": "2023-01-15",
            "property_type": "house",
            "price": 250000
        },
        {
            "address_id": str(uuid.uuid4()),
            "address_raw": "456 Sample Ave",
            "city_id": str(uuid.uuid4()),
            "sale_date": "2023-02-20",
            "property_type": "apartment",
            "price": 180000
        }
    ]

@patch('trackimmo.modules.client_processor.get_client_by_id')
@patch('trackimmo.modules.client_processor.update_client_cities')
@patch('trackimmo.modules.client_processor.scrape_properties_for_client')
@patch('trackimmo.modules.client_processor.assign_properties_to_client')
@patch('trackimmo.modules.client_processor.send_client_notification')
@patch('trackimmo.modules.client_processor.update_client_last_updated')
async def test_process_client_data(
    mock_update_last_updated,
    mock_send_notification,
    mock_assign_properties,
    mock_scrape_properties,
    mock_update_cities,
    mock_get_client,
    mock_client,
    mock_properties
):
    """Test the process_client_data function."""
    # Configure mocks
    mock_get_client.return_value = mock_client
    mock_update_cities.return_value = None
    mock_scrape_properties.return_value = None
    mock_assign_properties.return_value = mock_properties
    mock_send_notification.return_value = None
    mock_update_last_updated.return_value = None
    
    # Run the function
    result = await process_client_data(mock_client["client_id"])
    
    # Verify the function calls
    mock_get_client.assert_called_once_with(mock_client["client_id"])
    mock_update_cities.assert_called_once_with(mock_client)
    mock_scrape_properties.assert_called_once_with(mock_client)
    mock_assign_properties.assert_called_once_with(mock_client, 5)
    mock_send_notification.assert_called_once_with(mock_client, mock_properties)
    mock_update_last_updated.assert_called_once_with(mock_client["client_id"])
    
    # Verify the result
    assert result["success"] is True
    assert result["properties_assigned"] == 2
    assert result["client_id"] == mock_client["client_id"]

@patch('trackimmo.modules.client_processor.get_client_by_id')
async def test_process_client_data_inactive_client(mock_get_client):
    """Test processing an inactive client."""
    # Configure mock to return an inactive client
    mock_get_client.return_value = {"client_id": "123", "status": "inactive"}
    
    # Verify that an error is raised
    with pytest.raises(ValueError):
        await process_client_data("123")

@patch('trackimmo.modules.client_processor.DBManager')
def test_assign_properties_to_client(mock_db_manager, mock_client, mock_properties):
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
    result = assign_properties_to_client(mock_client, 3)
    
    # Verify the results
    assert len(result) == 2  # Should return both properties since only 2 available
    assert mock_table.insert.call_count == 2  # Should insert 2 client_address records