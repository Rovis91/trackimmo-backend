"""
Client processing API endpoints.
"""
from fastapi import APIRouter, Header, HTTPException, Depends, BackgroundTasks
from typing import Dict, Any, List, Optional
from pydantic import BaseModel
from datetime import datetime, timedelta
import uuid
import asyncio

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

class AddAddressesRequest(BaseModel):
    client_id: str
    count: Optional[int] = None  # If None, use client's subscription default

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
    progress: Optional[Dict[str, Any]] = None

class ClientProcessAsyncResponse(BaseModel):
    success: bool
    job_id: str
    client_id: str
    message: str = "Processing started"

class ClientPropertiesResponse(BaseModel):
    success: bool
    client_id: str
    properties: List[Dict[str, Any]] = []
    total_count: int = 0
    message: Optional[str] = None

class JobCleanupResponse(BaseModel):
    success: bool
    cleaned_jobs: int = 0
    message: str = "Job cleanup completed"

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
    
    try:
        # Update job status to processing
        await update_job_status(job_id, "processing")
        
        # Get client data
        client = await get_client_by_id(client_id)
        if not client or client["status"] != "active":
            raise ValueError(f"Client {client_id} not found or inactive")
        
        # Process the client data
        result = await process_client_data(client_id)
        
        # Update job status to completed (no result data stored)
        await update_job_status(job_id, "completed")
        logger.info(f"Completed background processing for client {client_id}, job {job_id}: {result['properties_assigned']} properties assigned")
        
    except Exception as e:
        error_message = str(e)
        logger.error(f"Error in background processing for client {client_id}, job {job_id}: {error_message}")
        
        # Update job status to failed
        await update_job_status(job_id, "failed", {"error_message": error_message})
        
        # Add to retry queue only if it's not a permanent error
        if not is_permanent_error(error_message):
            await add_to_retry_queue(client_id, error_message)

async def update_job_status(job_id: str, status: str, result_data: Dict[str, Any] = None):
    """Update job status in database."""
    try:
        with DBManager() as db:
            update_data = {
                "status": status,
                "updated_at": datetime.now().isoformat()
            }
            # Store result data in error_message field if it's an error, otherwise ignore
            if status == "failed" and result_data and "error_message" in result_data:
                update_data["error_message"] = result_data["error_message"]
            
            db.get_client().table("processing_jobs").update(update_data).eq("job_id", job_id).execute()
    except Exception as e:
        logger.error(f"Error updating job status for {job_id}: {str(e)}")

def is_permanent_error(error_message: str) -> bool:
    """Check if an error is permanent (shouldn't be retried)."""
    permanent_indicators = [
        "not found or inactive",
        "missing required",
        "invalid client",
        "no chosen cities",
        "no property types"
    ]
    return any(indicator in error_message.lower() for indicator in permanent_indicators)

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
        
        # Check if client already has a running job
        existing_job = await get_active_job_for_client(request.client_id)
        if existing_job:
            logger.info(f"Client {request.client_id} already has active job {existing_job['job_id']}")
            return {
                "success": True,
                "job_id": existing_job["job_id"],
                "client_id": request.client_id,
                "message": "Job already in progress"
            }
        
        # Create a new job record
        job_id = await create_new_job(request.client_id, "processing")
        
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

@router.post("/add-addresses", response_model=ClientProcessAsyncResponse)
async def add_addresses_to_client(
    request: AddAddressesRequest,
    background_tasks: BackgroundTasks,
    api_key: str = Depends(verify_api_key)
):
    """
    Add specific number of addresses to an existing client.
    """
    try:
        # Validate client exists
        client = await get_client_by_id(request.client_id)
        if not client or client["status"] != "active":
            raise HTTPException(status_code=404, detail=f"Client {request.client_id} not found or inactive")
        
        # Determine count
        count = request.count or client.get("addresses_per_report", 10)
        
        # Create job for adding addresses
        job_id = await create_new_job(request.client_id, "processing", {"requested_count": count})
        
        # Background task
        async def add_addresses_background():
            try:
                await update_job_status(job_id, "processing")
                
                from trackimmo.modules.client_processor import assign_properties_to_client
                new_addresses = await assign_properties_to_client(client, count)
                
                if new_addresses:
                    from trackimmo.utils.email_sender import send_client_notification
                    await send_client_notification(client, new_addresses)
                
                await update_job_status(job_id, "completed")
                
            except Exception as e:
                await update_job_status(job_id, "failed", {"error_message": str(e)})
        
        background_tasks.add_task(add_addresses_background)
        
        return {
            "success": True,
            "job_id": job_id,
            "client_id": request.client_id,
            "message": f"Adding {count} addresses"
        }
        
    except HTTPException as e:
        raise
    except Exception as e:
        logger.error(f"Error adding addresses for client {request.client_id}: {str(e)}")
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
            "failed": failed,
            "message": f"Processed {processed} jobs, {failed} failed"
        }
    except Exception as e:
        logger.error(f"Error processing retry queue: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/cleanup-jobs", response_model=JobCleanupResponse)
async def cleanup_completed_jobs(
    api_key: str = Depends(verify_api_key),
    older_than_days: int = 7
):
    """
    Clean up completed and failed jobs older than specified days.
    """
    try:
        cutoff_date = (datetime.now() - timedelta(days=older_than_days)).isoformat()
        
        with DBManager() as db:
            # Delete old completed/failed jobs
            response = db.get_client().table("processing_jobs") \
                .delete() \
                .in_("status", ["completed", "failed"]) \
                .lt("updated_at", cutoff_date) \
                .execute()
            
            cleaned_count = len(response.data) if response.data else 0
            
        logger.info(f"Cleaned up {cleaned_count} old jobs")
        
        return {
            "success": True,
            "cleaned_jobs": cleaned_count,
            "message": f"Cleaned {cleaned_count} jobs older than {older_than_days} days"
        }
        
    except Exception as e:
        logger.error(f"Error cleaning up jobs: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

async def get_active_job_for_client(client_id: str) -> Optional[Dict[str, Any]]:
    """Get active job for a client if exists."""
    try:
        with DBManager() as db:
            response = db.get_client().table("processing_jobs") \
                .select("*") \
                .eq("client_id", client_id) \
                .in_("status", ["processing", "pending"]) \
                .order("created_at", desc=True) \
                .limit(1) \
                .execute()
            
            if response.data and len(response.data) > 0:
                return response.data[0]
        return None
    except Exception as e:
        logger.error(f"Error getting active job for client {client_id}: {str(e)}")
        return None

async def create_new_job(client_id: str, status: str = "pending", initial_result: Dict = None) -> str:
    """Create a new processing job."""
    job_id = str(uuid.uuid4())
    now = datetime.now()
    
    job_data = {
        "job_id": job_id,
        "client_id": client_id,
        "status": status,
        "attempt_count": 1,
        "last_attempt": now.isoformat(),
        "next_attempt": (now + timedelta(hours=1)).isoformat(),
        "created_at": now.isoformat(),
        "updated_at": now.isoformat()
    }
    
    # Store initial error message if provided
    if initial_result and "error_message" in initial_result:
        job_data["error_message"] = initial_result["error_message"]
    
    with DBManager() as db:
        db.get_client().table("processing_jobs").insert(job_data).execute()
    
    return job_id

async def add_to_retry_queue(client_id: str, error_message: Optional[str] = None):
    """Add a client to the retry queue."""
    try:
        job_id = await create_new_job(client_id, "pending", {"error_message": error_message})
        logger.info(f"Added client {client_id} to retry queue with job ID {job_id}")
    except Exception as e:
        logger.error(f"Error adding client {client_id} to retry queue: {str(e)}")

async def _process_retry_queue():
    """Process jobs in the retry queue."""
    processed = 0
    failed = 0
    now = datetime.now()
    
    try:
        with DBManager() as db:
            # Get jobs due for retry
            response = db.get_client().table("processing_jobs").select("*") \
                .eq("status", "pending") \
                .lt("next_attempt", now.isoformat()) \
                .execute()
            
            for job in response.data:
                # If max retries reached, mark as failed permanently
                if job["attempt_count"] >= 3:
                    try:
                        from trackimmo.utils.email_sender import send_error_notification
                        send_error_notification(job["client_id"], job.get("error_message"))
                        
                        db.get_client().table("processing_jobs").update({
                            "status": "failed_permanent",
                            "updated_at": now.isoformat()
                        }).eq("job_id", job["job_id"]).execute()
                        
                        failed += 1
                        continue
                    except Exception as e:
                        logger.error(f"Error sending notification for job {job['job_id']}: {str(e)}")
                
                # Try processing
                try:
                    # Mark as processing
                    db.get_client().table("processing_jobs").update({
                        "status": "processing",
                        "attempt_count": job["attempt_count"] + 1,
                        "last_attempt": now.isoformat(),
                        "updated_at": now.isoformat()
                    }).eq("job_id", job["job_id"]).execute()
                    
                    # Process client
                    await process_client_background(job["job_id"], job["client_id"])
                    processed += 1
                    
                except Exception as e:
                    error_str = str(e)
                    attempt = job["attempt_count"] + 1
                    next_attempt = now + timedelta(hours=2**attempt)  # Exponential backoff
                    
                    if attempt >= 3 or is_permanent_error(error_str):
                        db.get_client().table("processing_jobs").update({
                            "status": "failed_permanent",
                            "attempt_count": attempt,
                            "last_attempt": now.isoformat(),
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
                        
    except Exception as e:
        logger.error(f"Error in retry queue processing: {str(e)}")
    
    return processed, failed

@router.get("/get-client-properties/{client_id}", response_model=ClientPropertiesResponse)
async def get_client_properties_endpoint(
    client_id: str,
    limit: Optional[int] = 100,
    offset: Optional[int] = 0,
    api_key: str = Depends(verify_api_key)
):
    """Get properties assigned to a client with pagination."""
    try:
        result = await get_client_properties(client_id, limit, offset)
        return result
    except Exception as e:
        logger.error(f"Error getting properties for client {client_id}: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

async def get_client_properties(client_id: str, limit: int = 100, offset: int = 0) -> Dict[str, Any]:
    """
    Get properties assigned to a client with pagination.
    
    Args:
        client_id: The client's UUID
        limit: Maximum number of properties to return
        offset: Number of properties to skip
        
    Returns:
        Dict with client properties
    """
    logger.info(f"Getting properties for client {client_id} (limit={limit}, offset={offset})")
    
    try:
        # Check if client exists and is active
        client = await get_client_by_id(client_id)
        if not client or client["status"] != "active":
            raise ValueError(f"Client {client_id} not found or inactive")
        
        # Get total count
        with DBManager() as db:
            count_response = db.get_client().table("client_addresses") \
                .select("address_id", count="exact") \
                .eq("client_id", client_id) \
                .execute()
            
            total_count = count_response.count or 0
            
            # Get properties with pagination
            ca_response = db.get_client().table("client_addresses") \
                .select("*, addresses(*)") \
                .eq("client_id", client_id) \
                .order("send_date", desc=True) \
                .range(offset, offset + limit - 1) \
                .execute()
            
            properties = []
            for ca in ca_response.data:
                if ca.get("addresses"):
                    prop = ca["addresses"]
                    prop["client_address_info"] = {
                        "status": ca.get("status"),
                        "send_date": ca.get("send_date"),
                        "notes": ca.get("notes")
                    }
                    properties.append(prop)
            
        return {
            "success": True,
            "client_id": client_id,
            "properties": properties,
            "total_count": total_count,
            "returned_count": len(properties)
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
            
            # Since we don't have a result column, we can't track properties_assigned
            # This would need to be tracked differently if needed
            properties_assigned = None
            progress = {}  # No progress tracking without result column
                
            return {
                "job_id": job["job_id"],
                "client_id": job["client_id"],
                "status": job["status"],
                "properties_assigned": properties_assigned,
                "error_message": job.get("error_message"),
                "created_at": datetime.fromisoformat(job["created_at"].replace('Z', '+00:00')),
                "updated_at": datetime.fromisoformat(job["updated_at"].replace('Z', '+00:00')),
                "progress": progress
            }
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting job status for {job_id}: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))