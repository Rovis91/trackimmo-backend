"""
Metrics utilities for tracking application performance.
"""
import time
from functools import wraps
from typing import Dict, Any, Callable, Optional
from prometheus_client import Counter, Histogram, Gauge, start_http_server
import threading
import atexit
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from trackimmo.utils.logger import get_logger

logger = get_logger(__name__)

# Initialize metrics
REQUEST_COUNT = Counter('trackimmo_request_count', 'Count of requests received', ['endpoint'])
REQUEST_LATENCY = Histogram('trackimmo_request_latency_seconds', 'Request latency in seconds', ['endpoint'])
ACTIVE_REQUESTS = Gauge('trackimmo_active_requests', 'Number of active requests')
SCRAPER_OPERATIONS = Counter('trackimmo_scraper_operations', 'Count of scraper operations', ['operation', 'success'])
PROCESSOR_OPERATIONS = Counter('trackimmo_processor_operations', 'Count of processor operations', ['operation', 'success'])
DB_OPERATIONS = Counter('trackimmo_db_operations', 'Count of database operations', ['operation', 'success'])
ERROR_COUNT = Counter('trackimmo_error_count', 'Count of errors', ['module', 'error_type'])
API_CACHE_SIZE = Gauge('trackimmo_api_cache_size', 'Size of API cache')

# Global metrics server state
_metrics_server_started = False
_metrics_server_lock = threading.Lock()

def start_metrics_server(port: int = 8001):
    """
    Start the metrics server if not already running.
    
    Args:
        port: Port to run the metrics server on
    """
    global _metrics_server_started
    with _metrics_server_lock:
        if not _metrics_server_started:
            start_http_server(port)
            _metrics_server_started = True
            logger.info(f"Metrics server started on port {port}")
            # Register shutdown function
            atexit.register(lambda: logger.info("Metrics server shutting down"))

def track_time(func_or_name: Optional[Callable] = None, metric_name: Optional[str] = None):
    """
    Decorator to track function execution time.
    Can be used as @track_time or @track_time(metric_name="custom_name")
    
    Args:
        func_or_name: Function to wrap or metric name
        metric_name: Custom metric name if not using function name
    """
    def decorator(func):
        name = metric_name or func.__name__
        
        @wraps(func)
        def wrapper(*args, **kwargs):
            ACTIVE_REQUESTS.inc()
            start_time = time.time()
            success = True
            try:
                result = func(*args, **kwargs)
                return result
            except Exception as e:
                success = False
                ERROR_COUNT.labels(module=func.__module__, error_type=type(e).__name__).inc()
                raise
            finally:
                duration = time.time() - start_time
                REQUEST_LATENCY.labels(endpoint=name).observe(duration)
                REQUEST_COUNT.labels(endpoint=name).inc()
                ACTIVE_REQUESTS.dec()
                if "scrape" in name.lower():
                    SCRAPER_OPERATIONS.labels(operation=name, success=str(success).lower()).inc()
                elif "process" in name.lower():
                    PROCESSOR_OPERATIONS.labels(operation=name, success=str(success).lower()).inc()
                elif any(db_op in name.lower() for db_op in ["db", "database", "sql", "query"]):
                    DB_OPERATIONS.labels(operation=name, success=str(success).lower()).inc()
        
        return wrapper
    
    # Handle both @track_time and @track_time("custom_name") syntaxes
    if callable(func_or_name):
        return decorator(func_or_name)
    else:
        if isinstance(func_or_name, str):
            metric_name = func_or_name
        return decorator

class MetricsMiddleware(BaseHTTPMiddleware):
    """Middleware for tracking API request metrics."""
    def __init__(self, app):
        super().__init__(app)

    async def dispatch(self, request: Request, call_next):
        ACTIVE_REQUESTS.inc()
        start_time = time.time()
        success = True
        try:
            response = await call_next(request)
            return response
        except Exception as e:
            success = False
            ERROR_COUNT.labels(module="api", error_type=type(e).__name__).inc()
            raise
        finally:
            duration = time.time() - start_time
            endpoint = request.url.path
            REQUEST_LATENCY.labels(endpoint=endpoint).observe(duration)
            REQUEST_COUNT.labels(endpoint=endpoint).inc()
            ACTIVE_REQUESTS.dec() 