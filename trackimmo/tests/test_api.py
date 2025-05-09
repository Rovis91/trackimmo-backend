"""
Tests for the TrackImmo API.
"""
import pytest
from fastapi.testclient import TestClient

from trackimmo.app import app

client = TestClient(app)


def test_health_endpoint():
    """Test the health endpoint."""
    response = client.get("/api/v1/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok" 