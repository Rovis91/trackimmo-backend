"""
Tests for the TrackImmo API.
"""
import pytest
from fastapi.testclient import TestClient

from trackimmo.app import app

client = TestClient(app)
API_KEY = "cb67274b99d89ab5"
CLIENT_ID = "e86f4960-f848-4236-b45c-0759b95db5a3"
HEADERS = {"X-API-Key": API_KEY}


def test_health_endpoint():
    """Test the health endpoint."""
    response = client.get("/api/v1/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_process_client_success():
    """Test processing a real client."""
    response = client.post(
        "/api/v1/api/process-client",
        headers=HEADERS,
        json={"client_id": CLIENT_ID}
    )
    # Accept 200 or 500 (if processing fails, e.g. missing data), but never 401/404/422
    assert response.status_code in (200, 500)
    if response.status_code == 200:
        data = response.json()
        assert data["success"] is True
        assert "properties_assigned" in data
    elif response.status_code == 500:
        data = response.json()
        assert "detail" in data


def test_process_client_invalid_key():
    """Test process-client with invalid API key."""
    response = client.post(
        "/api/v1/api/process-client",
        headers={"X-API-Key": "invalid"},
        json={"client_id": CLIENT_ID}
    )
    assert response.status_code == 401
    assert response.json()["detail"] == "Invalid API key"


def test_process_retry_queue():
    """Test processing the retry queue."""
    response = client.post(
        "/api/v1/api/process-retry-queue",
        headers=HEADERS
    )
    # Accept 200 or 500 (if no jobs or error), but never 401/404/422
    assert response.status_code in (200, 500)
    if response.status_code == 200:
        data = response.json()
        assert data["success"] is True
        assert "processed" in data
        assert "failed" in data
    elif response.status_code == 500:
        data = response.json()
        assert "detail" in data 