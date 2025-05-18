"""
Test the cron job functionality for TrackImmo.
"""
import pytest
from unittest.mock import patch, MagicMock, AsyncMock
import uuid
from datetime import datetime, timedelta
import requests

from trackimmo.scripts.run_daily_updates import (
    get_clients_for_update,
    is_last_day_of_month,
    main as cron_main
)

# Test client ID
TEST_CLIENT_ID = "e86f4960-f848-4236-b45c-0759b95db5a3"

# Test data
TEST_CLIENTS = [
    {
        "client_id": TEST_CLIENT_ID,
        "first_name": "Test",
        "last_name": "User",
        "email": "test@example.com",
        "status": "active",
        "send_day": 15  # 15th of each month
    },
    {
        "client_id": str(uuid.uuid4()),
        "first_name": "Another",
        "last_name": "User",
        "email": "another@example.com",
        "status": "active",
        "send_day": 30  # 30th of each month (not valid for February)
    },
    {
        "client_id": str(uuid.uuid4()),
        "first_name": "Inactive",
        "last_name": "User",
        "email": "inactive@example.com",
        "status": "inactive",
        "send_day": 15  # Inactive, should be skipped
    }
]

def test_matching_send_day():
    """Test that clients with matching send_day are correctly identified."""
    # Mock the today's date to be the 15th
    with patch('trackimmo.scripts.run_daily_updates.datetime') as mock_datetime:
        mock_datetime.now.return_value = datetime(2023, 5, 15)  # May 15th
        
        # Mock the database query
        with patch('trackimmo.scripts.run_daily_updates.DBManager') as mock_db_cls:
            # Setup the mock db
            mock_db = MagicMock()
            mock_db.__enter__.return_value = mock_db
            mock_db_cls.return_value = mock_db
            
            # Setup mock response
            mock_execute = MagicMock()
            mock_execute.data = [TEST_CLIENTS[0]]  # Just the first client (matches day 15)
            mock_db.get_client.return_value.table.return_value.select.return_value.eq.return_value.eq.return_value.execute.return_value = mock_execute
            
            # Call the function
            clients = get_clients_for_update(15)
            
            # Verify results
            assert len(clients) == 1
            assert clients[0]["client_id"] == TEST_CLIENT_ID

def test_non_matching_send_day():
    """Test that clients with non-matching send_day are correctly excluded."""
    # Mock the database query
    with patch('trackimmo.scripts.run_daily_updates.DBManager') as mock_db_cls:
        # Setup the mock db
        mock_db = MagicMock()
        mock_db.__enter__.return_value = mock_db
        mock_db_cls.return_value = mock_db
        
        # Setup mock response - empty for day 20
        mock_execute = MagicMock()
        mock_execute.data = []
        mock_db.get_client.return_value.table.return_value.select.return_value.eq.return_value.eq.return_value.execute.return_value = mock_execute
        
        # Call the function
        clients = get_clients_for_update(20)
        
        # Verify results
        assert len(clients) == 0

def test_last_day_of_month():
    """
    Test that is_last_day_of_month correctly identifies the last day.
    """
    # Mock for Feb 28, 2023 (last day of February)
    with patch('trackimmo.scripts.run_daily_updates.datetime') as mock_datetime:
        mock_datetime.now.return_value = datetime(2023, 2, 28)
        assert is_last_day_of_month() == True
        
    # Mock for Feb 27, 2023 (not the last day)
    with patch('trackimmo.scripts.run_daily_updates.datetime') as mock_datetime:
        mock_datetime.now.return_value = datetime(2023, 2, 27)
        assert is_last_day_of_month() == False

def test_month_end_includes_higher_days():
    """
    Test that clients with impossible dates (e.g., February 31)
    are included on the last day of the month.
    """
    # Set up mocks
    with patch('trackimmo.scripts.run_daily_updates.datetime') as mock_datetime, \
         patch('trackimmo.scripts.run_daily_updates.DBManager') as mock_db_cls, \
         patch('trackimmo.scripts.run_daily_updates.is_last_day_of_month') as mock_is_last_day:
        
        # Feb 28, 2023 (last day)
        mock_datetime.now.return_value = datetime(2023, 2, 28)
        mock_is_last_day.return_value = True
        
        # Setup the mock db
        mock_db = MagicMock()
        mock_db.__enter__.return_value = mock_db
        mock_db_cls.return_value = mock_db
        
        # First call for day 28 clients
        mock_execute1 = MagicMock()
        mock_execute1.data = [{"client_id": "client-day-28", "send_day": 28}]
        
        # Second call for day 29 clients
        mock_execute2 = MagicMock()
        mock_execute2.data = [{"client_id": "client-day-29", "send_day": 29}]
        
        # Third call for day 30 clients
        mock_execute3 = MagicMock()
        mock_execute3.data = [{"client_id": "client-day-30", "send_day": 30}]
        
        # Fourth call for day 31 clients
        mock_execute4 = MagicMock()
        mock_execute4.data = [{"client_id": "client-day-31", "send_day": 31}]
        
        # Setup the mock to return different results for different calls
        mock_db.get_client.return_value.table.return_value.select.return_value.eq.return_value.eq.return_value.execute.side_effect = [
            mock_execute1,  # First call (day 28)
            mock_execute2,  # Second call (day 29)
            mock_execute3,  # Third call (day 30)
            mock_execute4   # Fourth call (day 31)
        ]
        
        # Mock HTTP requests
        with patch('trackimmo.scripts.run_daily_updates.requests.post') as mock_post:
            mock_response = MagicMock()
            mock_response.raise_for_status.return_value = None
            mock_response.json.return_value = {"success": True}
            mock_post.return_value = mock_response
            
            # Mock sleep to avoid delays
            with patch('trackimmo.scripts.run_daily_updates.time.sleep'):
                # Run the main function
                cron_main()
                
                # Verify that all 4 clients were processed
                client_calls = [call for call in mock_post.call_args_list if '/api/process-client' in call[0][0]]
                assert len(client_calls) == 4

def test_error_handling():
    """
    Test that errors while processing clients are handled gracefully.
    """
    # Mock datetime to a specific day
    with patch('trackimmo.scripts.run_daily_updates.datetime') as mock_datetime, \
         patch('trackimmo.scripts.run_daily_updates.DBManager') as mock_db_cls:
        
        mock_datetime.now.return_value = datetime(2023, 5, 15)
        
        # Setup the mock db
        mock_db = MagicMock()
        mock_db.__enter__.return_value = mock_db
        mock_db_cls.return_value = mock_db
        
        # Setup mock response with two clients
        mock_execute = MagicMock()
        mock_execute.data = [TEST_CLIENTS[0], {"client_id": "problem-client", "send_day": 15}]
        mock_db.get_client.return_value.table.return_value.select.return_value.eq.return_value.eq.return_value.execute.return_value = mock_execute
        
        # Mock HTTP requests - first succeeds, second fails
        with patch('trackimmo.scripts.run_daily_updates.requests.post') as mock_post, \
             patch('trackimmo.scripts.run_daily_updates.logger') as mock_logger:
            
            # Setup mock response behavior
            def mock_post_side_effect(url, **kwargs):
                client_id = kwargs.get('json', {}).get('client_id')
                if client_id == "problem-client":
                    raise requests.exceptions.RequestException("API Error")
                
                mock_resp = MagicMock()
                mock_resp.raise_for_status.return_value = None
                mock_resp.json.return_value = {"success": True}
                return mock_resp
            
            mock_post.side_effect = mock_post_side_effect
            
            # Mock sleep to avoid delays
            with patch('trackimmo.scripts.run_daily_updates.time.sleep'):
                # Run the main function
                cron_main()
                
                # Verify that the error was logged
                error_calls = [call for call in mock_logger.error.call_args_list]
                assert len(error_calls) >= 1
                
                # Verify the retry queue was still processed
                retry_calls = [call for call in mock_post.call_args_list if '/api/process-retry-queue' in call[0][0]]
                assert len(retry_calls) == 1

def test_retry_queue_processing():
    """
    Test that the retry queue is processed after all clients.
    """
    # Mock datetime to a specific day
    with patch('trackimmo.scripts.run_daily_updates.datetime') as mock_datetime, \
         patch('trackimmo.scripts.run_daily_updates.DBManager') as mock_db_cls:
        
        mock_datetime.now.return_value = datetime(2023, 5, 15)
        
        # Setup the mock db
        mock_db = MagicMock()
        mock_db.__enter__.return_value = mock_db
        mock_db_cls.return_value = mock_db
        
        # Setup mock response with one client
        mock_execute = MagicMock()
        mock_execute.data = [TEST_CLIENTS[0]]
        mock_db.get_client.return_value.table.return_value.select.return_value.eq.return_value.eq.return_value.execute.return_value = mock_execute
        
        # Mock HTTP requests
        with patch('trackimmo.scripts.run_daily_updates.requests.post') as mock_post:
            mock_response = MagicMock()
            mock_response.raise_for_status.return_value = None
            mock_response.json.return_value = {"success": True, "processed": 2, "failed": 1}
            mock_post.return_value = mock_response
            
            # Mock sleep to avoid delays
            with patch('trackimmo.scripts.run_daily_updates.time.sleep'):
                # Run the main function
                cron_main()
                
                # Check the order of calls - client processing first, then retry queue
                assert len(mock_post.call_args_list) == 2
                assert '/api/process-client' in mock_post.call_args_list[0][0][0]
                assert '/api/process-retry-queue' in mock_post.call_args_list[1][0][0]

if __name__ == "__main__":
    # This allows running the tests directly
    pytest.main(["-xvs", __file__]) 