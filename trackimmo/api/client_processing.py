"""
Client processing API endpoints.
"""
from fastapi import APIRouter, Header, HTTPException, Depends, BackgroundTasks
from typing import Dict, Any, List, Optional
from pydantic import BaseModel
from datetime import datetime, timedelta
import uuid

from trackimmo.config import settings
from trackimmo.modules.client_processor import process_client_data, get_client_by_id
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
    client_id: Optional[str] = None

class JobStatusResponse(BaseModel):
    job_id: str
    client_id: str
    status: str
    properties_assigned: Optional[int] = None
    error_message: Optional[str] = None
    created_at: datetime
    updated_at: datetime

class ClientProcessAsyncResponse(BaseModel):
    success: bool
    job_id: str
    client_id: str
    message: str = "Processing started"

class ClientPropertiesResponse(BaseModel):
    success: bool
    client_id: str
    properties: List[Dict[str, Any]] = []
    message: Optional[str] = None

def verify_api_key(api_key: str = Header(None, alias="X-API-Key")):
    """Verify the API key."""
    if api_key != settings.API_KEY:
        logger.warning("Invalid API key attempt")
        raise HTTPException(status_code=401, detail="Invalid API key")
    return api_key

async def process_client_background(job_id: str, client_id: str):
    """
    Background task to process client data.
    
    Args:
        job_id: The job ID for tracking
        client_id: The client's UUID
    """
    logger.info(f"Starting background processing for client {client_id}, job {job_id}")
    now = datetime.now()
    
    try:
        # Get client data
        client = await get_client_by_id(client_id)
        if not client or client["status"] != "active":
            raise ValueError(f"Client {client_id} not found or inactive")
        
        # Process the client data
        result = await process_client_data(client_id)
        
        # Update job status to completed
        with DBManager() as db:
            db.get_client().table("processing_jobs").update({
                "status": "completed",
                "result": {"properties_assigned": result["properties_assigned"]},
                "updated_at": datetime.now().isoformat()
            }).eq("job_id", job_id).execute()
            
        logger.info(f"Completed background processing for client {client_id}, job {job_id}")
        
    except Exception as e:
        error_message = str(e)
        logger.error(f"Error in background processing for client {client_id}, job {job_id}: {error_message}")
        
        # Update job status to failed
        with DBManager() as db:
            db.get_client().table("processing_jobs").update({
                "status": "failed",
                "error_message": error_message,
                "updated_at": datetime.now().isoformat()
            }).eq("job_id", job_id).execute()
            
        # Add to retry queue
        add_to_retry_queue(client_id, error_message)

@router.post("/process-client", response_model=ClientProcessAsyncResponse)
async def process_client(
    request: ClientProcessRequest,
    background_tasks: BackgroundTasks,
    api_key: str = Depends(verify_api_key)
):
    """
    Process a client to assign new properties.
    
    This is an asynchronous endpoint that immediately returns a job ID
    and processes the client data in the background.
    """
    try:
        # Validate client exists
        client = await get_client_by_id(request.client_id)
        if not client or client["status"] != "active":
            raise HTTPException(status_code=404, detail=f"Client {request.client_id} not found or inactive")
        
        # Create a new job record
        job_id = str(uuid.uuid4())
        now = datetime.now()
        
        with DBManager() as db:
            db.get_client().table("processing_jobs").insert({
                "job_id": job_id,
                "client_id": request.client_id,
                "status": "processing",
                "attempt_count": 1,
                "last_attempt": now.isoformat(),
                "next_attempt": (now + timedelta(hours=1)).isoformat(),
                "created_at": now.isoformat(),
                "updated_at": now.isoformat()
            }).execute()
        
        # Add processing to background tasks
        background_tasks.add_task(process_client_background, job_id, request.client_id)
        
        logger.info(f"Started background processing for client {request.client_id}, job {job_id}")
        
        # Return job ID immediately
        return {
            "success": True,
            "job_id": job_id,
            "client_id": request.client_id
        }
        
    except HTTPException as e:
        # Re-raise HTTP exceptions
        raise
    except Exception as e:
        # Log the error
        logger.error(f"Error setting up processing for client {request.client_id}: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/process-retry-queue", response_model=Dict[str, Any])
async def process_retry_queue(
    api_key: str = Depends(verify_api_key)
):
    """Process the retry queue."""
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
        # Create a new job for retry
        job_id = str(uuid.uuid4())
        db.get_client().table("processing_jobs").insert({
            "job_id": job_id,
            "client_id": client_id,
            "status": "pending",
            "attempt_count": 0,
            "last_attempt": now.isoformat(),
            "next_attempt": next_attempt.isoformat(),
            "error_message": error_message,
            "created_at": now.isoformat(),
            "updated_at": now.isoformat()
        }).execute()
    
    logger.info(f"Added client {client_id} to retry queue with job ID {job_id}")

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
                client_id = job["client_id"]
                job_id = job["job_id"]
                await process_client_background(job_id, client_id)
                
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

@router.get("/get-client-properties/{client_id}", response_model=ClientPropertiesResponse)
async def get_client_properties_endpoint(
    client_id: str,
    api_key: str = Depends(verify_api_key)
):
    """Get properties assigned to a client."""
    try:
        result = await get_client_properties(client_id)
        return result
    except Exception as e:
        logger.error(f"Error getting properties for client {client_id}: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

async def get_client_properties(client_id: str) -> Dict[str, Any]:
    """
    Get properties assigned to a client.
    
    Args:
        client_id: The client's UUID
        
    Returns:
        Dict with client properties
    """
    logger.info(f"Getting properties for client {client_id}")
    
    try:
        # Check if client exists and is active
        client = await get_client_by_id(client_id)
        if not client or client["status"] != "active":
            raise ValueError(f"Client {client_id} not found or inactive")
        
        # Get properties assigned to the client
        with DBManager() as db:
            # Join client_properties and properties tables
            query = f"""
                SELECT p.* 
                FROM client_properties cp
                JOIN properties p ON cp.property_id = p.property_id
                WHERE cp.client_id = '{client_id}'
            """
            properties = db.get_client().rpc('get_client_properties', {'client_id_param': client_id}).execute()
            
        return {
            "success": True,
            "client_id": client_id,
            "properties": properties.data if properties.data else []
        }
    except Exception as e:
        logger.error(f"Error getting properties for client {client_id}: {str(e)}")
        raise

@router.get("/job-status/{job_id}", response_model=JobStatusResponse)
async def get_job_status(
    job_id: str,
    api_key: str = Depends(verify_api_key)
):
    """
    Get the status of a job by ID.
    
    Args:
        job_id: The UUID of the job to check
    
    Returns:
        Job status information
    """
    try:
        with DBManager() as db:
            response = db.get_client().table("processing_jobs").select("*").eq("job_id", job_id).execute()
            
            if not response.data or len(response.data) == 0:
                raise HTTPException(status_code=404, detail=f"Job {job_id} not found")
                
            job = response.data[0]
            
            # Process job data for response
            properties_assigned = None
            if job["status"] == "completed" and job.get("result") and "properties_assigned" in job["result"]:
                properties_assigned = job["result"]["properties_assigned"]
                
            return {
                "job_id": job["job_id"],
                "client_id": job["client_id"],
                "status": job["status"],
                "properties_assigned": properties_assigned,
                "error_message": job.get("error_message"),
                "created_at": datetime.fromisoformat(job["created_at"].replace('Z', '+00:00')),
                "updated_at": datetime.fromisoformat(job["updated_at"].replace('Z', '+00:00'))
            }
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting job status for {job_id}: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))