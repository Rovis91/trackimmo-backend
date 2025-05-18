"""
Test authentication for the TrackImmo API.
"""
import pytest
from fastapi.testclient import TestClient
import os
from unittest.mock import patch

from trackimmo.app import app
from trackimmo.config import settings

# Create a test client
client = TestClient(app)

# Test client ID to use for valid tests
TEST_CLIENT_ID = "e86f4960-f848-4236-b45c-0759b95db5a3"

@pytest.fixture
def valid_api_key():
    """Fixture to provide a valid API key."""
    # Use the API key from settings
    return settings.API_KEY

@pytest.fixture
def invalid_api_key():
    """Fixture to provide an invalid API key."""
    return "invalid-api-key-for-testing"

def test_valid_api_key(valid_api_key):
    """Test that a valid API key is accepted."""
    # Test the health endpoint with a valid API key
    response = client.get("/health", headers={"X-API-Key": valid_api_key})
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}

def test_invalid_api_key(invalid_api_key):
    """Test that an invalid API key is rejected."""
    # Test the process-client endpoint with an invalid API key
    response = client.post(
        "/api/process-client", 
        json={"client_id": TEST_CLIENT_ID}, 
        headers={"X-API-Key": invalid_api_key}
    )
    assert response.status_code == 401
    assert "Invalid API key" in response.json()["detail"]

def test_missing_api_key():
    """Test that a missing API key is rejected."""
    # Test the process-client endpoint without an API key
    response = client.post(
        "/api/process-client", 
        json={"client_id": TEST_CLIENT_ID}
    )
    assert response.status_code == 401
    assert "Invalid API key" in response.json()["detail"]

if __name__ == "__main__":
    # This allows running the tests directly
    pytest.main(["-xvs", __file__]) 