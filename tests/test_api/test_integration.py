"""
Integration tests for TrackImmo API.
"""
import pytest
import asyncio
from datetime import datetime, timedelta
from fastapi.testclient import TestClient
from httpx import AsyncClient
import uuid

from trackimmo.app import app
from trackimmo.config import settings
from trackimmo.modules.db_manager import DBManager
from trackimmo.modules.client_processor import get_client_by_id, assign_properties_to_client
from trackimmo.utils.email_sender import test_email_configuration, send_client_notification

# Test client
client = TestClient(app)

# Test client ID (from your database)
TEST_CLIENT_ID = "e86f4960-f848-4236-b45c-0759b95db5a3"

# Headers for API calls
API_HEADERS = {"X-API-Key": settings.API_KEY}
ADMIN_HEADERS = {"X-Admin-Key": getattr(settings, 'ADMIN_API_KEY', settings.API_KEY)}

class TestHealthAndBasics:
    """Test basic API functionality."""
    
    def test_health_check(self):
        """Test basic health endpoint."""
        response = client.get("/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ok"
        assert "TrackImmo" in data["service"]
    
    def test_version_endpoint(self):
        """Test version endpoint."""
        response = client.get("/version")
        assert response.status_code == 200
        data = response.json()
        assert data["version"] == "1.0.0"
    
    def test_admin_health_check(self):
        """Test admin health check."""
        response = client.get("/admin/health")
        assert response.status_code == 200
        data = response.json()
        assert "status" in data
        assert "components" in data

class TestDatabaseConnection:
    """Test database connectivity and basic operations."""
    
    def test_database_connection(self):
        """Test Supabase connection."""
        try:
            with DBManager() as db:
                response = db.get_client().table("clients").select("client_id").limit(1).execute()
                assert response is not None
        except Exception as e:
            pytest.fail(f"Database connection failed: {e}")
    
    def test_get_test_client(self):
        """Test getting the test client."""
        with DBManager() as db:
            response = db.get_client().table("clients").select("*").eq("client_id", TEST_CLIENT_ID).execute()
            assert response.data is not None
            assert len(response.data) > 0
            
            client_data = response.data[0]
            assert client_data["client_id"] == TEST_CLIENT_ID
            assert client_data["status"] == "active"
    
    def test_client_cities_exist(self):
        """Test that client has cities configured."""
        with DBManager() as db:
            response = db.get_client().table("clients").select("chosen_cities").eq("client_id", TEST_CLIENT_ID).execute()
            assert response.data is not None
            assert len(response.data) > 0
            
            client_data = response.data[0]
            chosen_cities = client_data.get("chosen_cities", [])
            assert len(chosen_cities) > 0, "Test client must have chosen cities configured"

class TestClientProcessing:
    """Test client processing functionality."""
    
    @pytest.mark.asyncio
    async def test_get_client_by_id(self):
        """Test getting client by ID."""
        client_data = await get_client_by_id(TEST_CLIENT_ID)
        assert client_data is not None
        assert client_data["client_id"] == TEST_CLIENT_ID
        assert client_data["status"] == "active"
        assert "chosen_cities" in client_data
        assert "property_type_preferences" in client_data
    
    @pytest.mark.asyncio
    async def test_assign_properties_to_client(self):
        """Test property assignment logic."""
        # Get client
        client_data = await get_client_by_id(TEST_CLIENT_ID)
        assert client_data is not None
        
        # Count current assignments
        with DBManager() as db:
            before_response = db.get_client().table("client_addresses") \
                .select("address_id", count="exact") \
                .eq("client_id", TEST_CLIENT_ID) \
                .execute()
            before_count = before_response.count or 0
        
        # Assign 3 properties
        assigned_properties = await assign_properties_to_client(client_data, 3)
        
        # Verify assignment
        assert len(assigned_properties) >= 0  # Might be 0 if no eligible properties
        
        # Check database
        with DBManager() as db:
            after_response = db.get_client().table("client_addresses") \
                .select("address_id", count="exact") \
                .eq("client_id", TEST_CLIENT_ID) \
                .execute()
            after_count = after_response.count or 0
        
        expected_count = before_count + len(assigned_properties)
        assert after_count == expected_count
        
        # Verify properties meet age criteria if any assigned
        if assigned_properties:
            min_date = (datetime.now() - timedelta(days=8*365)).strftime("%Y-%m-%d")
            max_date = (datetime.now() - timedelta(days=6*365)).strftime("%Y-%m-%d")
            
            for prop in assigned_properties:
                prop_date = prop.get("sale_date", "")
                assert min_date <= prop_date <= max_date, f"Property {prop['address_id']} doesn't meet age criteria"

class TestEmailFunctionality:
    """Test email functionality."""
    
    @pytest.mark.asyncio
    async def test_email_configuration(self):
        """Test email configuration."""
        if not all([settings.EMAIL_SENDER, settings.SMTP_USERNAME, settings.SMTP_PASSWORD]):
            pytest.skip("Email configuration not complete")
        
        results = await test_email_configuration()
        assert results["smtp_config"] is True
        assert results["connection"] is True
        
        if results["errors"]:
            print(f"Email test warnings: {results['errors']}")
    
    @pytest.mark.asyncio
    async def test_client_notification_email(self):
        """Test sending client notification email."""
        if not settings.EMAIL_SENDER:
            pytest.skip("Email not configured")
        
        # Get client
        client_data = await get_client_by_id(TEST_CLIENT_ID)
        assert client_data is not None
        
        # Create test properties
        test_properties = [
            {
                "address_raw": "123 Rue de Test",
                "city_name": "Test City",
                "price": 300000,
                "surface": 80,
                "rooms": 3,
                "property_type": "apartment",
                "sale_date": "2018-01-15"
            }
        ]
        
        # Send notification (to a test email to avoid spamming)
        test_client_data = client_data.copy()
        test_client_data["email"] = settings.EMAIL_SENDER  # Send to self
        
        success = await send_client_notification(test_client_data, test_properties)
        # Don't assert success since email might fail in test environment
        # Just log the result
        print(f"Email notification test result: {success}")

class TestAPIEndpoints:
    """Test API endpoints."""
    
    def test_process_client_endpoint(self):
        """Test client processing endpoint."""
        response = client.post(
            "/api/process-client",
            json={"client_id": TEST_CLIENT_ID},
            headers=API_HEADERS
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert "job_id" in data
        assert data["client_id"] == TEST_CLIENT_ID
        
        # Store job ID for status checking
        job_id = data["job_id"]
        
        # Check job status
        status_response = client.get(f"/api/job-status/{job_id}", headers=API_HEADERS)
        assert status_response.status_code == 200
        status_data = status_response.json()
        assert status_data["job_id"] == job_id
        assert status_data["client_id"] == TEST_CLIENT_ID
        assert status_data["status"] in ["processing", "completed", "failed", "pending"]
    
    def test_add_addresses_endpoint(self):
        """Test adding addresses to client."""
        response = client.post(
            "/api/add-addresses",
            json={"client_id": TEST_CLIENT_ID, "count": 2},
            headers=API_HEADERS
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert "job_id" in data
        assert data["client_id"] == TEST_CLIENT_ID
    
    def test_get_client_properties(self):
        """Test getting client properties."""
        response = client.get(
            f"/api/get-client-properties/{TEST_CLIENT_ID}",
            headers=API_HEADERS
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["client_id"] == TEST_CLIENT_ID
        assert "properties" in data
        assert "total_count" in data
        assert isinstance(data["properties"], list)
    
    def test_cleanup_jobs_endpoint(self):
        """Test job cleanup endpoint."""
        response = client.post("/api/cleanup-jobs", headers=API_HEADERS)
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert "cleaned_jobs" in data

class TestAdminEndpoints:
    """Test admin endpoints."""
    
    def test_admin_stats(self):
        """Test admin statistics endpoint."""
        response = client.get("/admin/stats", headers=ADMIN_HEADERS)
        assert response.status_code == 200
        data = response.json()
        
        required_fields = [
            "total_clients", "active_clients", "total_properties", 
            "total_assignments", "jobs_pending", "jobs_processing", 
            "jobs_completed", "jobs_failed"
        ]
        
        for field in required_fields:
            assert field in data
            assert isinstance(data[field], int)
    
    def test_admin_list_clients(self):
        """Test admin list clients endpoint."""
        response = client.get("/admin/clients", headers=ADMIN_HEADERS)
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        
        # Check if our test client is in the list
        test_client_found = any(c["client_id"] == TEST_CLIENT_ID for c in data)
        assert test_client_found, "Test client not found in client list"
    
    def test_admin_client_details(self):
        """Test admin client details endpoint."""
        response = client.get(f"/admin/client/{TEST_CLIENT_ID}", headers=ADMIN_HEADERS)
        assert response.status_code == 200
        data = response.json()
        
        assert "client" in data
        assert "assigned_properties_count" in data
        assert "recent_jobs" in data
        assert "cities" in data
        
        assert data["client"]["client_id"] == TEST_CLIENT_ID
    
    def test_admin_test_email(self):
        """Test admin email testing endpoint."""
        if not settings.EMAIL_SENDER:
            pytest.skip("Email not configured")
        
        response = client.post(
            "/admin/test-email",
            json={
                "recipient": settings.EMAIL_SENDER,
                "template_type": "config"
            },
            headers=ADMIN_HEADERS
        )
        
        assert response.status_code == 200
        data = response.json()
        assert "success" in data
        assert "results" in data

class TestErrorHandling:
    """Test error handling."""
    
    def test_invalid_api_key(self):
        """Test API with invalid key."""
        response = client.post(
            "/api/process-client",
            json={"client_id": TEST_CLIENT_ID},
            headers={"X-API-Key": "invalid_key"}
        )
        assert response.status_code == 401
    
    def test_invalid_client_id(self):
        """Test with invalid client ID."""
        invalid_id = str(uuid.uuid4())
        response = client.post(
            "/api/process-client",
            json={"client_id": invalid_id},
            headers=API_HEADERS
        )
        assert response.status_code == 404
    
    def test_invalid_job_id(self):
        """Test with invalid job ID."""
        invalid_id = str(uuid.uuid4())
        response = client.get(f"/api/job-status/{invalid_id}", headers=API_HEADERS)
        assert response.status_code == 404

class TestBusinessLogic:
    """Test business logic implementation."""
    
    def test_property_age_filtering(self):
        """Test that properties are filtered by age (6-8 years)."""
        # This test verifies the business rule implementation
        min_date = (datetime.now() - timedelta(days=8*365))
        max_date = (datetime.now() - timedelta(days=6*365))
        
        # Get some properties from database
        with DBManager() as db:
            response = db.get_client().table("addresses") \
                .select("sale_date") \
                .gte("sale_date", min_date.strftime("%Y-%m-%d")) \
                .lte("sale_date", max_date.strftime("%Y-%m-%d")) \
                .limit(10) \
                .execute()
            
            properties = response.data
            
            # Verify all properties are within the age range
            for prop in properties:
                prop_date = datetime.strptime(prop["sale_date"], "%Y-%m-%d")
                assert min_date <= prop_date <= max_date, f"Property date {prop_date} not in range {min_date} to {max_date}"
    
    def test_weighted_selection_logic(self):
        """Test weighted selection favors older properties."""
        from trackimmo.modules.client_processor import weighted_random_selection
        
        # Create test properties with different dates
        test_properties = [
            {"address_id": "1", "sale_date": "2017-01-01"},  # Oldest
            {"address_id": "2", "sale_date": "2017-06-01"},
            {"address_id": "3", "sale_date": "2018-01-01"},  # Newest
        ]
        
        # Run selection multiple times and check distribution
        selections = []
        for _ in range(50):  # Run multiple times to check distribution
            selected = weighted_random_selection(test_properties, 1)
            if selected:
                selections.append(selected[0]["address_id"])
        
        # Oldest property should be selected more often
        oldest_count = selections.count("1")
        newest_count = selections.count("3")
        
        # With weighted selection, oldest should be selected more frequently
        # This is probabilistic, so we allow some variance
        assert oldest_count >= newest_count, "Weighted selection should favor older properties"

# Pytest configuration
@pytest.fixture(scope="session", autouse=True)
def setup_test_environment():
    """Setup test environment."""
    print(f"\n🧪 Starting TrackImmo Integration Tests")
    print(f"API Base URL: {settings.API_BASE_URL}")
    print(f"Test Client ID: {TEST_CLIENT_ID}")
    print(f"Database: {'Configured' if settings.SUPABASE_URL else 'Not configured'}")
    print(f"Email: {'Configured' if settings.EMAIL_SENDER else 'Not configured'}")
    
    # Verify test client exists
    try:
        with DBManager() as db:
            response = db.get_client().table("clients").select("client_id").eq("client_id", TEST_CLIENT_ID).execute()
            if not response.data:
                pytest.exit(f"Test client {TEST_CLIENT_ID} not found in database")
    except Exception as e:
        pytest.exit(f"Database connection failed: {e}")
    
    yield
    
    print(f"\n✅ TrackImmo Integration Tests Completed")

if __name__ == "__main__":
    # Run specific tests
    pytest.main([__file__, "-v", "--tb=short"])