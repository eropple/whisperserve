"""Main FastAPI application module for WhisperServe."""
import time
from typing import Dict, Any

from fastapi import FastAPI, Depends, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
import structlog

from app.utils.config import AppConfig

# Configure logger
logger = structlog.get_logger()

def create_app(config: AppConfig) -> FastAPI:
    """Create and configure the FastAPI application."""
    # Create FastAPI app
    app = FastAPI(
        title="WhisperServe",
        description="Multi-tenant Whisper API service for speech-to-text transcription",
        version="0.1.0",
    )
    
    # Add CORS middleware
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    
    # Add request middleware to log requests
    @app.middleware("http")
    async def log_requests(request: Request, call_next):
        start_time = time.time()
        
        # Add request details to structured log context
        log = logger.bind(
            path=request.url.path,
            method=request.method,
            client_ip=request.client.host if request.client else None,
        )
        
        log.info("http_request_received")
        
        # Process the request
        response = await call_next(request)
        
        # Log request completion with timing
        duration_ms = (time.time() - start_time) * 1000
        log.info(
            "http_request_completed",
            status_code=response.status_code,
            duration_ms=round(duration_ms, 2)
        )
        
        return response
    
    # Health check endpoint
    @app.get("/health", tags=["Health"])
    async def health_check() -> Dict[str, Any]:
        """Health check endpoint to verify the API is running."""
        return {
            "status": "ok",
            "version": "0.1.0",
            "service": "whisperserve",
            "model_size": config.model.model_size,
        }
    
    # In a real implementation, you would include API routers here
    # For example:
    # from app.api.routes import jobs_router
    # app.include_router(jobs_router)
    
    return app
