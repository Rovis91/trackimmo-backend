"""
Test retry queue functionality for the TrackImmo API.
"""
import pytest
from fastapi.testclient import TestClient
from datetime import datetime, timedelta
from unittest.mock import patch, MagicMock

from trackimmo.app import app
from trackimmo.config import settings
from trackimmo.api.client_processing import add_to_retry_queue

# Create a test client
client = TestClient(app)

# Test client ID to use for valid tests
TEST_CLIENT_ID = "e86f4960-f848-4236-b45c-0759b95db5a3"

@pytest.fixture
def valid_api_key():
    """Fixture to provide a valid API key."""
    return settings.API_KEY

@pytest.fixture
def mock_db_manager():
    """Mock the DBManager to avoid actual database operations."""
    with patch('trackimmo.api.client_processing.DBManager') as mock_db_cls:
        # Create a mock instance of the DB client
        mock_db = MagicMock()
        mock_db.__enter__.return_value = mock_db
        mock_db_cls.return_value = mock_db
        
        # Create a mock table
        mock_table = MagicMock()
        mock_db.get_client.return_value.table.return_value = mock_table
        
        # Setup select mock
        mock_select = MagicMock()
        mock_table.select.return_value = mock_select
        mock_eq = MagicMock()
        mock_select.eq.return_value = mock_eq
        mock_lt = MagicMock()
        mock_select.lt.return_value = mock_lt
        
        # Setup insert/update mocks
        mock_insert = MagicMock()
        mock_table.insert.return_value = mock_insert
        mock_update = MagicMock()
        mock_table.update.return_value = mock_update
        
        yield mock_db

def test_add_to_retry_queue(mock_db_manager):
    """Test adding a client to the retry queue."""
    # Call the function
    add_to_retry_queue(TEST_CLIENT_ID, "Test error message")
    
    # Verify that the insert method was called with the correct parameters
    mock_table = mock_db_manager.get_client.return_value.table.return_value
    mock_table.insert.assert_called_once()
    
    # Extract the inserted data
    inserted_data = mock_table.insert.call_args[0][0]
    
    # Verify the data
    assert inserted_data["client_id"] == TEST_CLIENT_ID
    assert inserted_data["status"] == "pending"
    assert inserted_data["attempt_count"] == 0
    assert inserted_data["error_message"] == "Test error message"
    
    # Verify dates are set
    assert "last_attempt" in inserted_data
    assert "next_attempt" in inserted_data
    assert "created_at" in inserted_data
    assert "updated_at" in inserted_data

def test_process_retry_queue_empty(valid_api_key, mock_db_manager):
    """Test processing an empty retry queue."""
    # Setup the mock to return empty data
    mock_execute = MagicMock()
    mock_execute.data = []
    mock_db_manager.get_client.return_value.table.return_value.select.return_value.eq.return_value.lt.return_value.execute.return_value = mock_execute
    
    # Make the API call
    response = client.post(
        "/api/process-retry-queue", 
        headers={"X-API-Key": valid_api_key}
    )
    
    # Verify the response
    assert response.status_code == 200
    data = response.json()
    assert data["success"] == True
    assert data["processed"] == 0
    assert data["failed"] == 0

def test_process_retry_queue_with_jobs(valid_api_key, mock_db_manager):
    """Test processing a retry queue with pending jobs."""
    # Mock the _process_retry_queue function
    with patch('trackimmo.api.client_processing._process_retry_queue') as mock_process_queue:
        # Setup the mock to return successful processing results
        mock_process_queue.return_value = (1, 1)  # 1 processed, 1 failed
        
        # Make the API call
        response = client.post(
            "/api/process-retry-queue", 
            headers={"X-API-Key": valid_api_key}
        )
        
        # Verify the response
        assert response.status_code == 200
        data = response.json()
        assert data["success"] == True
        assert data["processed"] == 1
        assert data["failed"] == 1
        
        # Verify that _process_retry_queue was called
        mock_process_queue.assert_called_once()

def test_max_retries_reached(valid_api_key, mock_db_manager):
    """Test that a job is marked as failed when max retries is reached."""
    # Create a test job that has reached max retries
    now = datetime.now()
    test_job = {
        "job_id": "job3",
        "client_id": TEST_CLIENT_ID,
        "status": "pending",
        "attempt_count": 3,  # Max retries reached
        "last_attempt": (now - timedelta(hours=8)).isoformat(),
        "next_attempt": (now - timedelta(hours=1)).isoformat(),
        "error_message": "Previous error",
        "created_at": (now - timedelta(days=1)).isoformat(),
        "updated_at": (now - timedelta(hours=8)).isoformat()
    }
    
    # Setup the mock to return our test job
    mock_execute = MagicMock()
    mock_execute.data = [test_job]
    mock_db_manager.get_client.return_value.table.return_value.select.return_value.eq.return_value.lt.return_value.execute.return_value = mock_execute
    
    # Mock the send_error_notification function
    with patch('trackimmo.utils.email_sender.send_error_notification') as mock_notify:
        # Make the API call
        response = client.post(
            "/api/process-retry-queue", 
            headers={"X-API-Key": valid_api_key}
        )
        
        # Verify the response
        assert response.status_code == 200
        data = response.json()
        assert data["success"] == True
        assert data["processed"] == 0  # None processed
        assert data["failed"] == 1     # One failed
        
        # Verify that notification was sent
        mock_notify.assert_called_once_with(TEST_CLIENT_ID, "Previous error")
        
        # Verify that the job was marked as failed
        mock_update = mock_db_manager.get_client.return_value.table.return_value.update
        mock_update.assert_called_with({
            "status": "failed",
            "updated_at": mock_update.call_args[0][0]["updated_at"]  # Dynamic timestamp
        })

if __name__ == "__main__":
    # This allows running the tests directly
    pytest.main(["-xvs", __file__]) 