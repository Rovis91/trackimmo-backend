"""
Admin endpoints for TrackImmo API.
"""
from fastapi import APIRouter, Header, HTTPException, Depends
from typing import Dict, Any, List, Optional
from pydantic import BaseModel
from datetime import datetime, timedelta

from trackimmo.config import settings
from trackimmo.utils.logger import get_logger
from trackimmo.modules.db_manager import DBManager
from trackimmo.modules.client_processor import get_client_by_id, assign_properties_to_client
from trackimmo.utils.email_sender import (
    test_email_configuration,
    send_welcome_email,
    send_client_notification,
    send_error_notification_async,
    send_monthly_notification,
    send_insufficient_addresses_notification
)

logger = get_logger(__name__)

# Create router
router = APIRouter(prefix="/admin", tags=["admin"])

# Request models
class TestEmailRequest(BaseModel):
    recipient: str
    template_type: str = "notification"  # notification, welcome, error, monthly, insufficient

class TestClientProcessingRequest(BaseModel):
    client_id: str
    count: Optional[int] = 5

class SystemStatsResponse(BaseModel):
    total_clients: int
    active_clients: int
    total_properties: int
    total_assignments: int
    jobs_pending: int
    jobs_processing: int
    jobs_completed: int
    jobs_failed: int

def verify_admin_api_key(api_key: str = Header(None, alias="X-Admin-Key")):
    """Verify the admin API key."""
    admin_key = getattr(settings, 'ADMIN_API_KEY', settings.API_KEY)
    if api_key != admin_key:
        logger.warning("Invalid admin API key attempt")
        raise HTTPException(status_code=401, detail="Invalid admin API key")
    return api_key

@router.get("/health", response_model=Dict[str, Any])
async def admin_health_check():
    """Detailed health check for admin."""
    try:
        health_status = {
            "status": "ok",
            "timestamp": datetime.now().isoformat(),
            "components": {}
        }
        
        # Test database connection
        try:
            with DBManager() as db:
                response = db.get_client().table("clients").select("client_id", count="exact").limit(1).execute()
                health_status["components"]["database"] = {
                    "status": "ok",
                    "message": f"Connected, {response.count or 0} total clients"
                }
        except Exception as e:
            health_status["components"]["database"] = {
                "status": "error",
                "message": str(e)
            }
            health_status["status"] = "degraded"
        
        # Test email configuration
        try:
            email_test_results = await test_email_configuration()
            if email_test_results["smtp_config"] and email_test_results["connection"]:
                health_status["components"]["email"] = {
                    "status": "ok",
                    "message": "SMTP configuration valid"
                }
            else:
                health_status["components"]["email"] = {
                    "status": "warning",
                    "message": f"Issues: {', '.join(email_test_results['errors'])}"
                }
                health_status["status"] = "degraded"
        except Exception as e:
            health_status["components"]["email"] = {
                "status": "error",
                "message": str(e)
            }
            health_status["status"] = "degraded"
        
        return health_status
        
    except Exception as e:
        logger.error(f"Admin health check failed: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/stats", response_model=SystemStatsResponse)
async def get_system_stats(api_key: str = Depends(verify_admin_api_key)):
    """Get system statistics."""
    try:
        with DBManager() as db:
            # Get client stats
            clients_response = db.get_client().table("clients").select("status", count="exact").execute()
            total_clients = clients_response.count or 0
            
            active_response = db.get_client().table("clients").select("client_id", count="exact").eq("status", "active").execute()
            active_clients = active_response.count or 0
            
            # Get property stats
            properties_response = db.get_client().table("addresses").select("address_id", count="exact").execute()
            total_properties = properties_response.count or 0
            
            # Get assignment stats
            assignments_response = db.get_client().table("client_addresses").select("client_address_id", count="exact").execute()
            total_assignments = assignments_response.count or 0
            
            # Get job stats
            jobs_stats = {}
            for status in ["pending", "processing", "completed", "failed"]:
                job_response = db.get_client().table("processing_jobs").select("job_id", count="exact").eq("status", status).execute()
                jobs_stats[f"jobs_{status}"] = job_response.count or 0
        
        return SystemStatsResponse(
            total_clients=total_clients,
            active_clients=active_clients,
            total_properties=total_properties,
            total_assignments=total_assignments,
            **jobs_stats
        )
        
    except Exception as e:
        logger.error(f"Error getting system stats: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/test-email")
async def test_email_endpoint(
    request: TestEmailRequest,
    api_key: str = Depends(verify_admin_api_key)
):
    """Test email sending with different templates."""
    try:
        if request.template_type == "config":
            # Test configuration
            results = await test_email_configuration()
            return {
                "success": results["send_test"],
                "results": results,
                "message": "Configuration test completed"
            }
        
        elif request.template_type == "welcome":
            # Test welcome email
            test_client = {
                "first_name": "Test",
                "last_name": "User",
                "email": request.recipient,
                "subscription_type": "pro",
                "client_id": "test-client-id"
            }
            
            success = await send_welcome_email(test_client)
            return {
                "success": success,
                "message": f"Welcome email {'sent' if success else 'failed'} to {request.recipient}"
            }
        
        elif request.template_type == "notification":
            # Test notification email
            test_client = {
                "first_name": "Test",
                "last_name": "User",
                "email": request.recipient,
                "client_id": "test-client-id"
            }
            
            test_properties = [
                {
                    "address_raw": "123 Rue de la Paix",
                    "city_name": "Paris",
                    "price": 450000,
                    "surface": 75,
                    "rooms": 3,
                    "property_type": "apartment",
                    "sale_date": "2018-06-15"
                },
                {
                    "address_raw": "45 Avenue des Champs",
                    "city_name": "Lyon",
                    "price": 320000,
                    "surface": 95,
                    "rooms": 4,
                    "property_type": "house",
                    "sale_date": "2017-09-22"
                }
            ]
            
            success = await send_client_notification(test_client, test_properties)
            return {
                "success": success,
                "message": f"Notification email {'sent' if success else 'failed'} to {request.recipient}"
            }
        
        elif request.template_type == "monthly":
            # Test monthly notification email
            test_client = {
                "first_name": "Test",
                "last_name": "User",
                "email": request.recipient,
                "client_id": "test-client-id",
                "send_day": 15
            }
            
            success = await send_monthly_notification(test_client)
            return {
                "success": success,
                "message": f"Monthly notification email {'sent' if success else 'failed'} to {request.recipient}"
            }
        
        elif request.template_type == "insufficient":
            # Test insufficient addresses notification to CTO
            success = await send_insufficient_addresses_notification("test-client-id", 3, 10)
            return {
                "success": success,
                "message": f"Insufficient addresses notification {'sent' if success else 'failed'}"
            }
        
        elif request.template_type == "error":
            # Test error notification
            success = await send_error_notification_async("test-client-id", "This is a test error message")
            return {
                "success": success,
                "message": f"Error notification {'sent' if success else 'failed'}"
            }
        
        else:
            raise HTTPException(status_code=400, detail="Invalid template type. Valid types: config, welcome, notification, monthly, insufficient, error")
            
    except Exception as e:
        logger.error(f"Error testing email: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/test-client-processing")
async def test_client_processing(
    request: TestClientProcessingRequest,
    api_key: str = Depends(verify_admin_api_key)
):
    """Test client processing logic without full scraping."""
    try:
        # Get client
        client = await get_client_by_id(request.client_id)
        if not client:
            raise HTTPException(status_code=404, detail=f"Client {request.client_id} not found")
        
        if client["status"] != "active":
            raise HTTPException(status_code=400, detail=f"Client {request.client_id} is not active")
        
        # Test property assignment
        properties = await assign_properties_to_client(client, request.count)
        
        # Test email notification
        email_success = False
        if properties:
            email_success = await send_client_notification(client, properties)
        
        return {
            "success": True,
            "client_id": request.client_id,
            "properties_assigned": len(properties),
            "email_sent": email_success,
            "properties": properties[:3],  # Return first 3 for preview
            "message": f"Assigned {len(properties)} properties to {client['first_name']} {client['last_name']}"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error testing client processing: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/clients", response_model=List[Dict[str, Any]])
async def list_clients(
    api_key: str = Depends(verify_admin_api_key),
    status: Optional[str] = None,
    limit: int = 50,
    offset: int = 0
):
    """List clients with optional filtering."""
    try:
        with DBManager() as db:
            query = db.get_client().table("clients").select("*")
            
            if status:
                query = query.eq("status", status)
            
            response = query.order("created_at", desc=True).range(offset, offset + limit - 1).execute()
            
            return response.data
            
    except Exception as e:
        logger.error(f"Error listing clients: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/client/{client_id}")
async def get_client_details(
    client_id: str,
    api_key: str = Depends(verify_admin_api_key)
):
    """Get detailed client information."""
    try:
        client = await get_client_by_id(client_id)
        if not client:
            raise HTTPException(status_code=404, detail="Client not found")
        
        with DBManager() as db:
            # Get assigned properties count
            assignments_response = db.get_client().table("client_addresses") \
                .select("address_id", count="exact") \
                .eq("client_id", client_id) \
                .execute()
            
            assigned_count = assignments_response.count or 0
            
            # Get recent jobs
            jobs_response = db.get_client().table("processing_jobs") \
                .select("*") \
                .eq("client_id", client_id) \
                .order("created_at", desc=True) \
                .limit(5) \
                .execute()
            
            # Get cities info
            cities_info = []
            if client.get("chosen_cities"):
                cities_response = db.get_client().table("cities") \
                    .select("*") \
                    .in_("city_id", client["chosen_cities"]) \
                    .execute()
                cities_info = cities_response.data
        
        return {
            "client": client,
            "assigned_properties_count": assigned_count,
            "recent_jobs": jobs_response.data,
            "cities": cities_info
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting client details: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/jobs")
async def list_processing_jobs(
    api_key: str = Depends(verify_admin_api_key),
    status: Optional[str] = None,
    limit: int = 50,
    offset: int = 0
):
    """List processing jobs with optional filtering."""
    try:
        with DBManager() as db:
            query = db.get_client().table("processing_jobs").select("*, clients(first_name, last_name, email)")
            
            if status:
                query = query.eq("status", status)
            
            response = query.order("created_at", desc=True).range(offset, offset + limit - 1).execute()
            
            return response.data
            
    except Exception as e:
        logger.error(f"Error listing jobs: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.delete("/jobs/cleanup")
async def cleanup_old_jobs(
    api_key: str = Depends(verify_admin_api_key),
    older_than_days: int = 30
):
    """Clean up old completed and failed jobs."""
    try:
        cutoff_date = (datetime.now() - timedelta(days=older_than_days)).isoformat()
        
        with DBManager() as db:
            # Delete old jobs
            response = db.get_client().table("processing_jobs") \
                .delete() \
                .in_("status", ["completed", "failed", "failed_permanent"]) \
                .lt("updated_at", cutoff_date) \
                .execute()
            
            deleted_count = len(response.data) if response.data else 0
        
        logger.info(f"Cleaned up {deleted_count} old jobs")
        
        return {
            "success": True,
            "deleted_jobs": deleted_count,
            "message": f"Deleted {deleted_count} jobs older than {older_than_days} days"
        }
        
    except Exception as e:
        logger.error(f"Error cleaning up jobs: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/client/{client_id}/reset-assignments")
async def reset_client_assignments(
    client_id: str,
    api_key: str = Depends(verify_admin_api_key)
):
    """Reset all assignments for a client (for testing)."""
    try:
        client = await get_client_by_id(client_id)
        if not client:
            raise HTTPException(status_code=404, detail="Client not found")
        
        with DBManager() as db:
            # Delete all assignments for this client
            response = db.get_client().table("client_addresses") \
                .delete() \
                .eq("client_id", client_id) \
                .execute()
            
            deleted_count = len(response.data) if response.data else 0
        
        logger.info(f"Reset {deleted_count} assignments for client {client_id}")
        
        return {
            "success": True,
            "deleted_assignments": deleted_count,
            "message": f"Reset {deleted_count} assignments for client"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error resetting client assignments: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))