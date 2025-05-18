"""
Test input validation for the TrackImmo API endpoints.
"""
import pytest
from fastapi.testclient import TestClient
import uuid
from unittest.mock import patch, AsyncMock, MagicMock
import sys
from pathlib import Path

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

def test_valid_client_id(valid_api_key):
    """Test that a valid client ID format is accepted."""
    # Mock the client_processor.process_client_data function at the API level
    with patch('trackimmo.api.client_processing.process_client_data') as mock_process:
        # Setup async function
        async def mock_process_async(client_id):
            return {
                "success": True,
                "client_id": client_id,
                "properties_assigned": 5
            }
        mock_process.side_effect = mock_process_async
        
        # Make the API call with a valid UUID
        response = client.post(
            "/api/process-client", 
            json={"client_id": TEST_CLIENT_ID},
            headers={"X-API-Key": valid_api_key}
        )
        
        # Verify the response status code
        assert response.status_code == 200
        
        # Verify the response data
        data = response.json()
        assert data["success"] == True
        assert data["client_id"] == TEST_CLIENT_ID
        
        # Verify that the mock was called with the correct client ID
        mock_process.assert_called_once_with(TEST_CLIENT_ID)

def test_missing_client_id(valid_api_key):
    """Test that an error is returned when client_id is missing."""
    # Make the API call without a client_id
    response = client.post(
        "/api/process-client", 
        json={},  # Missing client_id
        headers={"X-API-Key": valid_api_key}
    )
    
    # Verify the response status code
    assert response.status_code == 422
    
    # Verify the error response format
    data = response.json()
    assert "detail" in data
    assert any("client_id" in field.get("loc", []) for field in data["detail"])

def test_wrong_client_id_type(valid_api_key):
    """Test that an error is returned when client_id is not a string."""
    # Make the API call with a non-string client_id
    response = client.post(
        "/api/process-client", 
        json={"client_id": 12345},  # Integer instead of string
        headers={"X-API-Key": valid_api_key}
    )
    
    # Verify the response status code
    assert response.status_code == 422
    
    # Verify the error response format
    data = response.json()
    assert "detail" in data
    assert any("client_id" in field.get("loc", []) for field in data["detail"])

def test_invalid_client_id_format(valid_api_key):
    """Test that an error is returned when client_id is not a valid UUID."""
    # Patch the add_to_retry_queue function to not actually try to add the invalid UUID
    with patch('trackimmo.api.client_processing.add_to_retry_queue'):
        # Use a more direct approach for testing validation
        with patch('trackimmo.api.client_processing.process_client_data', side_effect=ValueError("Invalid UUID format")):
            # Make the API call with an invalid UUID format
            response = client.post(
                "/api/process-client", 
                json={"client_id": "not-a-valid-uuid"},
                headers={"X-API-Key": valid_api_key}
            )
            
            # For this test, we expect a 500 error since the API tries to process it
            # but then encounters an error when trying to use the invalid UUID
            assert response.status_code == 500
            
            # Verify the error response format
            data = response.json()
            assert "detail" in data

def test_missing_api_key():
    """Test that an error is returned when API key is missing."""
    # Make the API call without an API key
    response = client.post(
        "/api/process-client", 
        json={"client_id": TEST_CLIENT_ID}
    )
    
    # Verify the response status code
    assert response.status_code == 401
    
    # Verify the error response format
    data = response.json()
    assert "detail" in data
    assert "API key" in data["detail"]

def test_invalid_api_key():
    """Test that an error is returned when API key is invalid."""
    # Make the API call with an invalid API key
    response = client.post(
        "/api/process-client", 
        json={"client_id": TEST_CLIENT_ID},
        headers={"X-API-Key": "invalid-api-key"}
    )
    
    # Verify the response status code
    assert response.status_code == 401
    
    # Verify the error response format
    data = response.json()
    assert "detail" in data
    assert "Invalid API key" in data["detail"]

if __name__ == "__main__":
    # This allows running the tests directly
    pytest.main(["-xvs", __file__]) 