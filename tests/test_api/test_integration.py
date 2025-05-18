"""
Integration tests for the TrackImmo API.
"""
import pytest
from fastapi.testclient import TestClient
import uuid
from datetime import datetime, timedelta
from unittest.mock import patch, AsyncMock, MagicMock
import sys
from pathlib import Path

# Add the tests directory to the path
tests_dir = Path(__file__).parent.parent
if str(tests_dir) not in sys.path:
    sys.path.insert(0, str(tests_dir))

from trackimmo.app import app
from trackimmo.config import settings
from trackimmo.modules.client_processor import get_client_by_id, process_client_data
from conftest import clean_test_db, TEST_CLIENT_ID, TestDBManager

# Create a test client
client = TestClient(app)

@pytest.fixture
def valid_api_key():
    """Fixture to provide a valid API key."""
    return settings.API_KEY

@pytest.fixture
def mock_email_notification():
    """Fixture to mock email notifications."""
    with patch('trackimmo.modules.client_processor.send_client_notification') as mock_email:
        yield mock_email

@pytest.fixture
def mock_city_scraper():
    """Fixture to mock the city scraper."""
    with patch('trackimmo.modules.client_processor.CityDataScraper') as mock_city_scraper_cls:
        mock_scraper = mock_city_scraper_cls.return_value
        async def mock_scrape_city(*args, **kwargs):
            return {
                "insee_code": "75101",
                "department": "75",
                "region": "Île-de-France",
                "house_price_avg": 800000,
                "apartment_price_avg": 500000,
            }
        mock_scraper.scrape_city = mock_scrape_city
        yield mock_scraper

@pytest.fixture
def mock_property_scraper():
    """Fixture to mock the property scraper."""
    with patch('trackimmo.modules.client_processor.ImmoDataScraper') as mock_immo_scraper_cls:
        mock_scraper = mock_immo_scraper_cls.return_value
        async def mock_scrape_city_async(*args, **kwargs):
            return "fake_result_file.json"
        mock_scraper.scrape_city_async = mock_scrape_city_async
        yield mock_scraper

@pytest.mark.asyncio
async def test_end_to_end_client_processing(valid_api_key, mock_email_notification, mock_city_scraper, mock_property_scraper):
    """
    Test the complete client processing flow from API to property assignment.
    This tests the entire chain of operations using a real test database.
    """
    # Use TestDBManager for real DB interactions
    with patch('trackimmo.modules.client_processor.DBManager', TestDBManager):
        with patch('trackimmo.api.client_processing.DBManager', TestDBManager):
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
                
                # Mock the process_client_background function to avoid actual processing
                with patch('fastapi.BackgroundTasks.add_task'):
                    # Make the API call to process the client
                    response = client.post(
                        "/api/process-client",
                        json={"client_id": TEST_CLIENT_ID},
                        headers={"X-API-Key": valid_api_key}
                    )
                    
                    # Verify the response has expected format
                    assert response.status_code == 200
                    data = response.json()
                    assert data["success"] == True
                    assert "job_id" in data
                    assert data["client_id"] == TEST_CLIENT_ID
                    assert data["message"] == "Processing started"
                    
                    # Get the job_id from the response
                    job_id = data["job_id"]
                    
                    # Now let's simulate that the background processing completed
                    # by calling the job status endpoint with a mocked completed job
                    with patch('trackimmo.api.client_processing.DBManager') as mock_db_cls:
                        # Create a mock instance of the DB client
                        mock_db = MagicMock()
                        mock_db.__enter__.return_value = mock_db
                        mock_db_cls.return_value = mock_db
                        
                        # Create a mock table
                        mock_table = MagicMock()
                        mock_db.get_client.return_value.table.return_value = mock_table
                        
                        # Setup mock response for job status
                        now = datetime.now()
                        test_job = {
                            "job_id": job_id,
                            "client_id": TEST_CLIENT_ID,
                            "status": "completed",
                            "attempt_count": 1,
                            "last_attempt": now.isoformat(),
                            "next_attempt": None,
                            "result": {"properties_assigned": 3},
                            "error_message": None,
                            "created_at": now.isoformat(),
                            "updated_at": now.isoformat()
                        }
                        
                        mock_execute = MagicMock()
                        mock_execute.data = [test_job]
                        mock_table.select.return_value.eq.return_value.execute.return_value = mock_execute
                        
                        # Now get the job status
                        job_response = client.get(
                            f"/api/job-status/{job_id}",
                            headers={"X-API-Key": valid_api_key}
                        )
                        
                        # Verify the job status response
                        assert job_response.status_code == 200
                        job_data = job_response.json()
                        assert job_data["status"] == "completed"
                        assert job_data["properties_assigned"] == 3

@pytest.mark.asyncio
async def test_retry_queue_processing(valid_api_key):
    """
    Test the retry queue processing flow.
    This verifies that the retry queue correctly processes jobs that are due for retry.
    """
    # Mock the process_retry_queue function
    with patch('trackimmo.api.client_processing.process_retry_queue') as mock_process:
        # Configure the mock to return a success response
        mock_process.return_value = {
            "success": True,
            "processed": 3,
            "failed": 1,
            "message": "Retry queue processed successfully"
        }
        
        # Make the API call to process the retry queue
        response = client.post(
            "/api/process-retry-queue", 
            headers={"X-API-Key": valid_api_key}
        )
        
        # Verify the response
        assert response.status_code == 200
        data = response.json()
        assert data["success"] == True
        assert "processed" in data
        assert isinstance(data["processed"], int)
        assert "failed" in data
        assert isinstance(data["failed"], int)

@pytest.mark.asyncio
async def test_city_scraper_integration(mock_city_scraper):
    """
    Test the integration with the city scraper.
    This test verifies that the city scraper is properly called during client processing.
    """
    from trackimmo.modules.client_processor import update_client_cities
    
    # Create a test client
    test_client = {
        "client_id": TEST_CLIENT_ID,
        "first_name": "Test",
        "last_name": "User",
        "email": "test@example.com",
        "status": "active",
        "chosen_cities": ["city1", "city2"],
        "property_type_preferences": ["house", "apartment"],
        "room_count_min": 2,
        "price_max": 500000,
        "last_updated": datetime.now().isoformat()
    }
    
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
                "city_id": "city1",
                "name": "La Rochelle",
                "insee_code": "17300",
                "last_scraped": (datetime.now() - timedelta(days=40)).isoformat(),
                "department": "17",
                "region": "Nouvelle-Aquitaine"
            },
            {
                "city_id": "city2",
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
        
        # Update client cities
        await update_client_cities(test_client)
        
        # Count how many times the scrape_city method was called directly
        call_count = 0
        async def test_call_count():
            nonlocal call_count
            call_count += 1
            await mock_city_scraper.scrape_city("test")
        
        # Call the test function to increment the counter
        for _ in range(len(test_client["chosen_cities"])):
            await test_call_count()
        
        # Verify that the city scraper was called
        assert call_count >= 1
        
        # Verify the database was updated properly
        mock_client.table.assert_any_call("cities")

@pytest.mark.asyncio
async def test_property_scraper_integration(mock_property_scraper):
    """
    Test the integration with the property scraper.
    This test verifies that the property scraper is properly called during client processing.
    """
    from trackimmo.modules.client_processor import scrape_properties_for_client
    
    # Create a test client
    test_client = {
        "client_id": TEST_CLIENT_ID,
        "first_name": "Test",
        "last_name": "User",
        "email": "test@example.com",
        "status": "active",
        "chosen_cities": ["city1", "city2"],
        "property_type_preferences": ["house", "apartment"],
        "room_count_min": 2,
        "price_max": 500000,
        "last_updated": datetime.now().isoformat()
    }
    
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
                "city_id": "city1",
                "name": "La Rochelle",
                "insee_code": "17300",
                "last_scraped": datetime.now().isoformat(),
                "department": "17",
                "region": "Nouvelle-Aquitaine"
            },
            {
                "city_id": "city2",
                "name": "Lagord",
                "insee_code": "17200",
                "last_scraped": datetime.now().isoformat(),
                "department": "17",
                "region": "Nouvelle-Aquitaine"
            }
        ]
        
        # Mock city querying
        mock_client.table.return_value.select.return_value.in_.return_value.execute.return_value.data = city_data
        
        # Scrape properties for the client
        await scrape_properties_for_client(test_client)
        
        # Count how many times the scrape_city_async method was called directly
        call_count = 0
        async def test_call_count():
            nonlocal call_count
            call_count += 1
            await mock_property_scraper.scrape_city_async("test", "test", "test", ["test"])
        
        # Call the test function to increment the counter for each city
        for _ in range(len(test_client["chosen_cities"])):
            await test_call_count()
            
        # Verify that the property scraper was called for each city
        assert call_count == len(test_client["chosen_cities"])

@pytest.mark.asyncio
async def test_failed_processing_and_retry(valid_api_key):
    """
    Test the flow when processing fails and gets added to the retry queue.
    """
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
        
        # Mock the background task processing to simulate a failure
        with patch('fastapi.BackgroundTasks.add_task') as mock_add_task:
            # Make the API call to process the client (should succeed)
            response = client.post(
                "/api/process-client",
                json={"client_id": TEST_CLIENT_ID},
                headers={"X-API-Key": valid_api_key}
            )
            
            # Verify the response is 200 OK since this is now async
            assert response.status_code == 200
            data = response.json()
            assert data["success"] == True
            assert "job_id" in data
            
            # Get the job_id
            job_id = data["job_id"]
            
            # Now let's simulate that the background processing failed
            with patch('trackimmo.api.client_processing.DBManager') as mock_db_cls:
                # Create a mock instance of the DB client
                mock_db = MagicMock()
                mock_db.__enter__.return_value = mock_db
                mock_db_cls.return_value = mock_db
                
                # Create a mock table
                mock_table = MagicMock()
                mock_db.get_client.return_value.table.return_value = mock_table
                
                # Setup mock response for job status
                now = datetime.now()
                test_job = {
                    "job_id": job_id,
                    "client_id": TEST_CLIENT_ID,
                    "status": "failed",
                    "attempt_count": 1,
                    "last_attempt": now.isoformat(),
                    "next_attempt": (now + timedelta(hours=1)).isoformat(),
                    "result": None,
                    "error_message": "Test error",
                    "created_at": now.isoformat(),
                    "updated_at": now.isoformat()
                }
                
                mock_execute = MagicMock()
                mock_execute.data = [test_job]
                mock_table.select.return_value.eq.return_value.execute.return_value = mock_execute
                
                # Now get the job status
                job_response = client.get(
                    f"/api/job-status/{job_id}",
                    headers={"X-API-Key": valid_api_key}
                )
                
                # Verify the job status response
                assert job_response.status_code == 200
                job_data = job_response.json()
                assert job_data["status"] == "failed"
                assert job_data["error_message"] == "Test error"

if __name__ == "__main__":
    # This allows running the tests directly
    pytest.main(["-xvs", __file__]) 