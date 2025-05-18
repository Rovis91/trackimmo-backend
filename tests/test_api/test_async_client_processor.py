"""
Test the asynchronous client processing functionality.
"""
import pytest
from fastapi.testclient import TestClient
from unittest.mock import patch, MagicMock, AsyncMock
import uuid
from datetime import datetime, timedelta

from trackimmo.app import app
from trackimmo.config import settings
from trackimmo.api.client_processing import process_client_background

# Create a test client
client = TestClient(app)

# Test data
TEST_CLIENT_ID = "e86f4960-f848-4236-b45c-0759b95db5a3"
TEST_JOB_ID = "f86f4960-f848-4236-b45c-0759b95db5b3"

@pytest.fixture
def valid_api_key():
    """Fixture to provide a valid API key."""
    return settings.API_KEY

@pytest.fixture
def mock_background_tasks():
    """Mock BackgroundTasks to verify it's called correctly."""
    with patch('trackimmo.api.client_processing.BackgroundTasks') as mock_bg_tasks:
        mock_instance = mock_bg_tasks.return_value
        yield mock_instance

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
        
        # Setup mock responses
        mock_execute = MagicMock()
        mock_execute.data = [{
            "client_id": TEST_CLIENT_ID,
            "status": "active",
            "first_name": "Test",
            "last_name": "User"
        }]
        mock_table.select.return_value.eq.return_value.execute.return_value = mock_execute
        
        yield mock_db

@pytest.fixture
def mock_get_client():
    """Mock get_client_by_id to return a valid client."""
    with patch('trackimmo.api.client_processing.get_client_by_id') as mock_get:
        async def mock_get_client_impl(client_id):
            return {
                "client_id": TEST_CLIENT_ID,
                "status": "active",
                "first_name": "Test",
                "last_name": "User"
            }
        mock_get.side_effect = mock_get_client_impl
        yield mock_get

@pytest.fixture
def mock_uuid():
    """Mock uuid.uuid4() to return a predictable value."""
    with patch('uuid.uuid4') as mock_uuid:
        mock_uuid.return_value = TEST_JOB_ID
        yield mock_uuid

def test_process_client_async(valid_api_key, mock_db_manager, mock_get_client, mock_uuid):
    """Test the asynchronous client processing endpoint."""
    # Mock BackgroundTasks directly in FastAPI
    with patch('fastapi.BackgroundTasks.add_task') as mock_add_task:
        # Make the API call
        response = client.post(
            "/api/process-client",
            json={"client_id": TEST_CLIENT_ID},
            headers={"X-API-Key": valid_api_key}
        )
        
        # Verify the response
        assert response.status_code == 200
        data = response.json()
        assert data["success"] == True
        assert data["job_id"] == TEST_JOB_ID
        assert data["client_id"] == TEST_CLIENT_ID
        
        # Verify the job was created in the database
        mock_table = mock_db_manager.get_client.return_value.table.return_value
        mock_table.insert.assert_called_once()
        
        # Verify job data
        job_data = mock_table.insert.call_args[0][0]
        assert job_data["job_id"] == TEST_JOB_ID
        assert job_data["client_id"] == TEST_CLIENT_ID
        assert job_data["status"] == "processing"
        assert job_data["attempt_count"] == 1
        
        # Verify that the background task was added (called at least once)
        assert mock_add_task.called

@pytest.mark.asyncio
async def test_background_processing(mock_db_manager, mock_get_client):
    """Test the background processing function."""
    # Mock process_client_data to return a successful result
    with patch('trackimmo.api.client_processing.process_client_data') as mock_process:
        async def mock_process_impl(client_id):
            return {
                "success": True,
                "properties_assigned": 5,
                "client_id": client_id
            }
        mock_process.side_effect = mock_process_impl
        
        # Call the background function
        await process_client_background(TEST_JOB_ID, TEST_CLIENT_ID)
        
        # Verify process_client_data was called with the correct parameters
        mock_process.assert_called_once_with(TEST_CLIENT_ID)
        
        # Verify the job was updated to completed
        mock_table = mock_db_manager.get_client.return_value.table.return_value
        mock_table.update.assert_called_once()
        
        # Verify update data
        update_data = mock_table.update.call_args[0][0]
        assert update_data["status"] == "completed"
        assert update_data["result"]["properties_assigned"] == 5

@pytest.mark.asyncio
async def test_background_processing_error(mock_db_manager, mock_get_client):
    """Test the background processing function with an error."""
    # Mock process_client_data to raise an exception
    with patch('trackimmo.api.client_processing.process_client_data') as mock_process:
        async def mock_process_impl(client_id):
            raise ValueError("Test error")
        mock_process.side_effect = mock_process_impl
        
        # Mock add_to_retry_queue to verify it's called
        with patch('trackimmo.api.client_processing.add_to_retry_queue') as mock_retry:
            # Call the background function
            await process_client_background(TEST_JOB_ID, TEST_CLIENT_ID)
            
            # Verify process_client_data was called with the correct parameters
            mock_process.assert_called_once_with(TEST_CLIENT_ID)
            
            # Verify the job was updated to failed
            mock_table = mock_db_manager.get_client.return_value.table.return_value
            mock_table.update.assert_called_once()
            
            # Verify update data
            update_data = mock_table.update.call_args[0][0]
            assert update_data["status"] == "failed"
            assert update_data["error_message"] == "Test error"
            
            # Verify add_to_retry_queue was called
            mock_retry.assert_called_once_with(TEST_CLIENT_ID, "Test error")

def test_get_job_status(valid_api_key, mock_db_manager):
    """Test getting the status of a job."""
    # Setup mock to return a job
    now = datetime.now()
    test_job = {
        "job_id": TEST_JOB_ID,
        "client_id": TEST_CLIENT_ID,
        "status": "completed",
        "attempt_count": 1,
        "last_attempt": now.isoformat(),
        "next_attempt": None,
        "result": {"properties_assigned": 5},
        "error_message": None,
        "created_at": now.isoformat(),
        "updated_at": now.isoformat()
    }
    
    mock_execute = MagicMock()
    mock_execute.data = [test_job]
    mock_db_manager.get_client.return_value.table.return_value.select.return_value.eq.return_value.execute.return_value = mock_execute
    
    # Make the API call
    response = client.get(
        f"/api/job-status/{TEST_JOB_ID}",
        headers={"X-API-Key": valid_api_key}
    )
    
    # Verify the response
    assert response.status_code == 200
    data = response.json()
    assert data["job_id"] == TEST_JOB_ID
    assert data["client_id"] == TEST_CLIENT_ID
    assert data["status"] == "completed"
    assert data["properties_assigned"] == 5
    assert data["error_message"] is None

def test_get_job_status_not_found(valid_api_key, mock_db_manager):
    """Test getting the status of a non-existent job."""
    # Setup mock to return no job
    mock_execute = MagicMock()
    mock_execute.data = []
    mock_db_manager.get_client.return_value.table.return_value.select.return_value.eq.return_value.execute.return_value = mock_execute
    
    # Make the API call
    response = client.get(
        f"/api/job-status/{TEST_JOB_ID}",
        headers={"X-API-Key": valid_api_key}
    )
    
    # Verify the response
    assert response.status_code == 404
    data = response.json()
    assert "detail" in data
    assert f"Job {TEST_JOB_ID} not found" in data["detail"]

if __name__ == "__main__":
    # This allows running the tests directly
    pytest.main(["-xvs", __file__]) 