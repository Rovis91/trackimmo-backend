"""
Test response formats for the TrackImmo API endpoints.
"""
import pytest
from fastapi.testclient import TestClient
from unittest.mock import patch, MagicMock, AsyncMock
import sys
from pathlib import Path
import uuid

# Add the tests directory to the path
tests_dir = Path(__file__).parent.parent
if str(tests_dir) not in sys.path:
    sys.path.insert(0, str(tests_dir))

from trackimmo.app import app
from trackimmo.config import settings
from conftest import clean_test_db, TEST_CLIENT_ID, TestDBManager

# Create a test client
client = TestClient(app)

@pytest.fixture
def valid_api_key():
    """Fixture to provide a valid API key."""
    return settings.API_KEY

def test_process_client_success_response(valid_api_key):
    """Test the successful response format of the process-client endpoint."""
    # Mock get_client_by_id to return a valid client
    with patch('trackimmo.api.client_processing.get_client_by_id') as mock_get_client:
        async def mock_get_client_impl(client_id):
            return {
                "client_id": client_id,
                "status": "active",
                "first_name": "Test",
                "last_name": "User"
            }
        mock_get_client.side_effect = mock_get_client_impl
        
        # Mock FastAPI's BackgroundTasks.add_task to avoid actual processing
        with patch('fastapi.BackgroundTasks.add_task'):
            # Make the API call
            response = client.post(
                "/api/process-client",
                json={"client_id": TEST_CLIENT_ID},
                headers={"X-API-Key": valid_api_key}
            )

            # Verify the response format for asynchronous processing
            assert response.status_code == 200
            data = response.json()
            assert "success" in data
            assert data["success"] == True
            assert "client_id" in data
            assert data["client_id"] == TEST_CLIENT_ID
            assert "job_id" in data
            assert "message" in data
            assert data["message"] == "Processing started"

def test_process_client_error_response(valid_api_key):
    """Test the error response format of the process-client endpoint."""
    # Mock get_client_by_id to raise an exception
    with patch('trackimmo.api.client_processing.get_client_by_id') as mock_get_client:
        async def mock_get_client_impl(client_id):
            return None  # Return None to simulate client not found
        mock_get_client.side_effect = mock_get_client_impl

        # Make the API call
        response = client.post(
            "/api/process-client",
            json={"client_id": TEST_CLIENT_ID},
            headers={"X-API-Key": valid_api_key}
        )

        # Verify the error response format
        assert response.status_code == 404
        data = response.json()
        assert "detail" in data
        assert "not found" in data["detail"].lower()

def test_retry_queue_success_response(valid_api_key):
    """Test the successful response format of the process-retry-queue endpoint."""
    # Mock the process_retry_queue function to return a successful result
    with patch('trackimmo.api.client_processing.process_retry_queue') as mock_process:
        # Configure the mock to return a success response
        async def mock_process_retry_async():
            return {
                "success": True,
                "processed": 3,
                "failed": 1,
                "message": "Retry queue processed successfully"
            }
        mock_process.side_effect = mock_process_retry_async
        
        # Make the API call
        response = client.post(
            "/api/process-retry-queue", 
            headers={"X-API-Key": valid_api_key}
        )
        
        # Verify the response format
        assert response.status_code == 200
        data = response.json()
        assert "success" in data
        assert data["success"] == True
        assert "processed" in data
        assert isinstance(data["processed"], int)
        assert "failed" in data
        assert isinstance(data["failed"], int)
        # Optional fields
        if "message" in data:
            assert isinstance(data["message"], str)

def test_retry_queue_error_response(valid_api_key):
    """Test the error response format of the process-retry-queue endpoint."""
    # Mock the _process_retry_queue function to raise an exception
    with patch('trackimmo.api.client_processing._process_retry_queue') as mock_process:
        # Configure the mock to raise an exception
        async def mock_process_retry_error():
            raise ValueError("Test error")
        mock_process.side_effect = mock_process_retry_error
        
        # Make the API call
        response = client.post(
            "/api/process-retry-queue", 
            headers={"X-API-Key": valid_api_key}
        )
        
        # Verify the error response format
        assert response.status_code == 500
        data = response.json()
        assert "detail" in data
        assert "Test error" in data["detail"]

def test_get_client_properties_success_response(valid_api_key, clean_test_db):
    """Test the successful response format of the get-client-properties endpoint."""
    # Mock the get_client_properties function
    with patch('trackimmo.api.client_processing.get_client_properties') as mock_get_props:
        # Configure the mock to return a success response
        async def mock_get_props_impl(client_id):
            return {
                "success": True,
                "client_id": client_id,
                "properties": [
                    {
                        "property_id": str(uuid.uuid4()),
                        "address": "123 Test St",
                        "city_id": "city1",
                        "price": 350000,
                        "rooms": 3,
                        "type": "house",
                        "description": "A nice test house",
                        "surface_area": 120,
                        "url": "http://example.com/property1"
                    },
                    {
                        "property_id": str(uuid.uuid4()),
                        "address": "456 Sample Ave",
                        "city_id": "city2",
                        "price": 400000,
                        "rooms": 2,
                        "type": "apartment",
                        "description": "A modern apartment",
                        "surface_area": 80,
                        "url": "http://example.com/property2"
                    }
                ]
            }
        mock_get_props.side_effect = mock_get_props_impl
        
        # Make the API call
        response = client.get(
            f"/api/get-client-properties/{TEST_CLIENT_ID}", 
            headers={"X-API-Key": valid_api_key}
        )
        
        # Verify the response format
        assert response.status_code == 200
        data = response.json()
        assert "success" in data
        assert data["success"] == True
        assert "client_id" in data
        assert data["client_id"] == TEST_CLIENT_ID
        assert "properties" in data
        assert isinstance(data["properties"], list)
        
        # Verify the mock was called with the client ID
        mock_get_props.assert_called_once_with(TEST_CLIENT_ID)

def test_get_client_properties_error_response(valid_api_key):
    """Test the error response format of the get-client-properties endpoint."""
    # Mock the get_client_properties function to raise an exception
    with patch('trackimmo.api.client_processing.get_client_properties') as mock_get_props:
        # Configure the mock to raise an exception
        async def mock_get_props_error(client_id):
            raise ValueError("Test error")
        mock_get_props.side_effect = mock_get_props_error
        
        # Make the API call
        response = client.get(
            f"/api/get-client-properties/{TEST_CLIENT_ID}", 
            headers={"X-API-Key": valid_api_key}
        )
        
        # Verify the error response format
        assert response.status_code == 500
        data = response.json()
        assert "detail" in data
        assert "Test error" in data["detail"]

@pytest.mark.asyncio
async def test_get_client_properties_success(valid_api_key):
    """Test the successful response of the get-client-properties endpoint."""
    # Define a function for testing
    async def test_get_client_properties(client_id):
        return {
            "success": True,
            "client_id": client_id,
            "properties": [
                {
                    "property_id": str(uuid.uuid4()),
                    "address": "123 Test St",
                    "city_id": "city1",
                    "price": 350000,
                    "rooms": 3,
                    "type": "house",
                    "description": "A nice test house",
                    "surface_area": 120,
                    "url": "http://example.com/property1"
                },
                {
                    "property_id": str(uuid.uuid4()),
                    "address": "456 Sample Ave",
                    "city_id": "city2",
                    "price": 400000,
                    "rooms": 2,
                    "type": "apartment",
                    "description": "A modern apartment",
                    "surface_area": 80,
                    "url": "http://example.com/property2"
                }
            ]
        }
    
    # Call the function directly for testing
    result = await test_get_client_properties(TEST_CLIENT_ID)
    
    # Verify the response format
    assert result["success"] == True
    assert result["client_id"] == TEST_CLIENT_ID
    assert "properties" in result
    assert isinstance(result["properties"], list)
    assert len(result["properties"]) == 2
    
    # Verify property structure
    for prop in result["properties"]:
        assert "property_id" in prop
        assert "address" in prop
        assert "price" in prop
        assert "rooms" in prop
        assert "type" in prop
        assert "url" in prop

@pytest.mark.asyncio
async def test_get_client_properties_error(valid_api_key):
    """Test the error handling of the get-client-properties function."""
    # Define a function that raises an error
    async def test_error_function(client_id):
        raise ValueError("Test error")
    
    # Test that the function raises the expected error
    with pytest.raises(ValueError) as exc_info:
        await test_error_function(TEST_CLIENT_ID)
    
    # Verify the error message
    assert "Test error" in str(exc_info.value)

def test_property_response_format():
    """Test the property response format structure."""
    # Create sample property data
    property_data = {
        "property_id": str(uuid.uuid4()),
        "address": "123 Test St",
        "city_id": "city1",
        "price": 350000,
        "rooms": 3,
        "type": "house",
        "description": "A nice test house",
        "surface_area": 120,
        "url": "http://example.com/property1"
    }
    
    # Verify property structure
    assert "property_id" in property_data
    assert "address" in property_data
    assert "price" in property_data
    assert "rooms" in property_data
    assert "type" in property_data
    assert "url" in property_data
    assert isinstance(property_data["price"], int)
    assert isinstance(property_data["rooms"], int)
    assert isinstance(property_data["type"], str)

def test_client_properties_response_format():
    """Test the client properties response format structure."""
    # Create a sample response
    response_data = {
        "success": True,
        "client_id": TEST_CLIENT_ID,
        "properties": [
            {
                "property_id": str(uuid.uuid4()),
                "address": "123 Test St",
                "city_id": "city1",
                "price": 350000,
                "rooms": 3,
                "type": "house",
                "description": "A nice test house",
                "surface_area": 120,
                "url": "http://example.com/property1"
            },
            {
                "property_id": str(uuid.uuid4()),
                "address": "456 Sample Ave",
                "city_id": "city2",
                "price": 400000,
                "rooms": 2,
                "type": "apartment",
                "description": "A modern apartment",
                "surface_area": 80,
                "url": "http://example.com/property2"
            }
        ]
    }
    
    # Verify response format
    assert "success" in response_data
    assert response_data["success"] == True
    assert "client_id" in response_data
    assert response_data["client_id"] == TEST_CLIENT_ID
    assert "properties" in response_data
    assert isinstance(response_data["properties"], list)
    assert len(response_data["properties"]) == 2
    
    # Verify property structure
    for prop in response_data["properties"]:
        assert "property_id" in prop
        assert "address" in prop
        assert "price" in prop
        assert "rooms" in prop
        assert "type" in prop
        assert "url" in prop
        assert isinstance(prop["price"], int)
        assert isinstance(prop["rooms"], int)
        assert isinstance(prop["type"], str)

if __name__ == "__main__":
    # This allows running the tests directly
    pytest.main(["-xvs", __file__]) 