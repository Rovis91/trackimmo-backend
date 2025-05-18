"""
Main application module for TrackImmo backend.

This module sets up the FastAPI application.
"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.openapi.utils import get_openapi

from trackimmo.api.routes import router
from trackimmo.config import settings
from trackimmo.utils.logger import get_logger
from trackimmo.utils.metrics import MetricsMiddleware, start_metrics_server

logger = get_logger(__name__)


def create_app() -> FastAPI:
    """Create and configure the FastAPI application."""
    # Create FastAPI app
    app = FastAPI(
        title=settings.PROJECT_NAME,
        description="API for TrackImmo - Real estate data scraping and enrichment",
        version="1.0.0",
        docs_url="/docs",
        redoc_url="/redoc",
        openapi_url="/openapi.json",
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
            version="1.0.0",
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


@app.on_event("startup")
async def startup_event():
    """Run code on application startup."""
    logger.info("Starting TrackImmo API")
    # Start metrics server on a separate port
    start_metrics_server(port=settings.METRICS_PORT if hasattr(settings, 'METRICS_PORT') else 8001)


@app.on_event("shutdown")
async def shutdown_event():
    """Run code on application shutdown."""
    logger.info("Shutting down TrackImmo API")


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