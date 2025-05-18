"""
Client processing API endpoints.
"""
from fastapi import APIRouter, Header, HTTPException, Depends
from typing import Dict, Any, List, Optional
from pydantic import BaseModel
from datetime import datetime, timedelta

from trackimmo.config import settings
from trackimmo.modules.client_processor import process_client_data
from trackimmo.utils.logger import get_logger
from trackimmo.modules.db_manager import DBManager

logger = get_logger(__name__)

# Create router
router = APIRouter(prefix="/api", tags=["client-processing"])

# Request models
class ClientProcessRequest(BaseModel):
    client_id: str

# Response models
class ClientProcessResponse(BaseModel):
    success: bool
    properties_assigned: int = 0
    message: Optional[str] = None

def verify_api_key(api_key: str = Header(None, alias="X-API-Key")):
    """Verify the API key."""
    if api_key != settings.API_KEY:
        logger.warning("Invalid API key attempt")
        raise HTTPException(status_code=401, detail="Invalid API key")
    return api_key

@router.post("/process-client", response_model=ClientProcessResponse)
async def process_client(
    request: ClientProcessRequest,
    api_key: str = Depends(verify_api_key)
):
    """Process a client to assign new properties."""
    try:
        # Process the client
        result = await process_client_data(request.client_id)
        return {
            "success": True,
            "properties_assigned": result["properties_assigned"]
        }
    except Exception as e:
        # Log the error
        logger.error(f"Error processing client {request.client_id}: {str(e)}")
        # Add to retry queue
        add_to_retry_queue(request.client_id, str(e))
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/process-retry-queue", response_model=Dict[str, Any])
async def process_retry_queue(
    api_key: str = Depends(verify_api_key)
):
    """Process the retry queue."""
    processed = 0
    failed = 0
    
    try:
        # Process the retry queue
        processed, failed = await _process_retry_queue()
        return {
            "success": True,
            "processed": processed,
            "failed": failed
        }
    except Exception as e:
        logger.error(f"Error processing retry queue: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

def add_to_retry_queue(client_id: str, error_message: Optional[str] = None):
    """Add a client to the retry queue."""
    now = datetime.now()
    next_attempt = now + timedelta(hours=1)  # First retry after 1 hour
    
    with DBManager() as db:
        db.get_client().table("processing_jobs").insert({
            "client_id": client_id,
            "status": "pending",
            "attempt_count": 0,
            "last_attempt": now.isoformat(),
            "next_attempt": next_attempt.isoformat(),
            "error_message": error_message,
            "created_at": now.isoformat(),
            "updated_at": now.isoformat()
        }).execute()
    
    logger.info(f"Added client {client_id} to retry queue")

async def _process_retry_queue():
    """Process jobs in the retry queue."""
    processed = 0
    failed = 0
    now = datetime.now()
    
    with DBManager() as db:
        # Get jobs due for retry
        response = db.get_client().table("processing_jobs").select("*") \
            .eq("status", "pending") \
            .lt("next_attempt", now.isoformat()) \
            .execute()
        
        for job in response.data:
            # If max retries reached, send notification and mark failed
            if job["attempt_count"] >= 3:
                from trackimmo.utils.email_sender import send_error_notification
                send_error_notification(job["client_id"], job["error_message"])
                db.get_client().table("processing_jobs").update({
                    "status": "failed",
                    "updated_at": now.isoformat()
                }).eq("job_id", job["job_id"]).execute()
                failed += 1
                continue
            # Try processing
            try:
                # Mark as processing
                db.get_client().table("processing_jobs").update({
                    "status": "processing",
                    "updated_at": now.isoformat()
                }).eq("job_id", job["job_id"]).execute()
                # Process client
                await process_client_data(job["client_id"])
                # Mark as completed
                db.get_client().table("processing_jobs").update({
                    "status": "completed",
                    "updated_at": now.isoformat()
                }).eq("job_id", job["job_id"]).execute()
                processed += 1
            except Exception as e:
                # If the error is permanent (e.g., client not found or inactive), mark as failed
                error_str = str(e)
                permanent_error = (
                    "not found or inactive" in error_str.lower() or
                    "missing required" in error_str.lower()
                )
                attempt = job["attempt_count"] + 1
                next_attempt = now + timedelta(hours=2**attempt)  # Exponential backoff
                if attempt >= 3 or permanent_error:
                    db.get_client().table("processing_jobs").update({
                        "status": "failed",
                        "attempt_count": attempt,
                        "last_attempt": now.isoformat(),
                        "next_attempt": next_attempt.isoformat(),
                        "error_message": error_str,
                        "updated_at": now.isoformat()
                    }).eq("job_id", job["job_id"]).execute()
                    failed += 1
                else:
                    db.get_client().table("processing_jobs").update({
                        "status": "pending",
                        "attempt_count": attempt,
                        "last_attempt": now.isoformat(),
                        "next_attempt": next_attempt.isoformat(),
                        "error_message": error_str,
                        "updated_at": now.isoformat()
                    }).eq("job_id", job["job_id"]).execute()
                    failed += 1
    return processed, failed