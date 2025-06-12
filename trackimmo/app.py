"""
Main application module for TrackImmo backend.

This module sets up the FastAPI application.
"""
import sys
import asyncio
import os

# Critical: Fix Windows event loop policy BEFORE any other imports
# This must be done before importing any modules that use asyncio
if sys.platform.startswith("win"):
    try:
        # Set the event loop policy to WindowsSelectorEventLoop for Playwright compatibility
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
        
        # Also set some Windows-specific environment variables for better subprocess handling
        os.environ.setdefault('PYTHONASYNCIODEBUG', '0')
        
        print("✓ Windows event loop policy configured for Playwright compatibility")
    except Exception as e:
        print(f"Warning: Could not set Windows event loop policy: {e}")

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.openapi.utils import get_openapi
from contextlib import asynccontextmanager

from trackimmo.api.routes import router
from trackimmo.config import settings
from trackimmo.utils.logger import get_logger
from trackimmo.utils.metrics import MetricsMiddleware, start_metrics_server

logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Starting TrackImmo API")
    start_metrics_server(port=settings.METRICS_PORT if hasattr(settings, 'METRICS_PORT') else 8001)
    yield
    logger.info("Shutting down TrackImmo API")


def create_app() -> FastAPI:
    """Create and configure the FastAPI application"""
    app = FastAPI(
        title=settings.PROJECT_NAME,
        description="API for TrackImmo - Real estate data scraping and enrichment",
        version="1.0.1",
        docs_url="/docs",
        redoc_url="/redoc",
        openapi_url="/openapi.json",
        lifespan=lifespan
    )
    
    # Configure CORS
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.CORS_ORIGINS,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    
    # Add metrics middleware
    app.add_middleware(MetricsMiddleware)
    
    # Include routers
    app.include_router(router, prefix=settings.API_V1_STR)
    app.router.include_router(router)
    # Customize OpenAPI schema
    def custom_openapi():
        if app.openapi_schema:
            return app.openapi_schema
        
        openapi_schema = get_openapi(
            title=settings.PROJECT_NAME,
            version="1.0.1",
            description="API for TrackImmo - Real estate data scraping and enrichment",
            routes=app.routes,
        )
        
        # Add response format
        openapi_schema["components"]["schemas"]["StandardResponse"] = {
            "type": "object",
            "properties": {
                "success": {"type": "boolean"},
                "data": {"type": "object"},
                "error": {
                    "type": "object",
                    "nullable": True,
                    "properties": {
                        "code": {"type": "string"},
                        "message": {"type": "string"}
                    }
                }
            }
        }
        
        app.openapi_schema = openapi_schema
        return app.openapi_schema
    
    app.openapi = custom_openapi
    
    return app


app = create_app()


if __name__ == "__main__":
    import uvicorn
    
    logger.info("Running TrackImmo API directly")
    uvicorn.run(
        "trackimmo.app:app",
        host="0.0.0.0",
        port=8000,
        reload=settings.DEBUG,
        log_level=settings.LOG_LEVEL.lower(),
    ) 