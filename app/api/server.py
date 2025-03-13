"""Main FastAPI application module for WhisperServe."""
import time
from typing import Dict, Any

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import HTTPBearer
import structlog
from uuid import uuid4

from app.api.otel_setup import setup_opentelemetry
from app.logging import get_logger, bind_logger_context, clear_logger_context
from app.utils.config import AppConfig
from app.utils.jwt_utils import extract_tenant_id_from_request

# Configure logger
logger = get_logger(__name__)

def create_app(config: AppConfig) -> FastAPI:
    """Create and configure the FastAPI application."""
    # Create FastAPI app
    app = FastAPI(
        title="WhisperServe",
        description="Multi-tenant Whisper API service for speech-to-text transcription",
        version="0.1.0",
    )
    
    # Define security scheme
    security_scheme = HTTPBearer(auto_error=False)
    
    # Add CORS middleware
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    
    # Add request middleware to log requests and add correlation IDs
    @app.middleware("http")
    async def request_middleware(request: Request, call_next):
        # Generate unique request ID for correlation
        request_id = request.headers.get("X-Request-ID", str(uuid4()))
        
        # Create context for this request
        log_context = {
            "request_id": request_id,
            "path": request.url.path,
            "method": request.method,
            "client_ip": request.client.host if request.client else None,
        }
        
        # Try to extract tenant ID for logging using our utility function
        # We pass raise_exceptions=False to avoid exceptions during logging context setup
        tenant_id = extract_tenant_id_from_request(request, config.jwt, raise_exceptions=False)
        if tenant_id:
            log_context["tenant_id"] = tenant_id
        
        # Bind variables to context for this request
        bind_logger_context(**log_context)
        
        # If OpenTelemetry is enabled, add trace context to logs
        if config.telemetry.enabled:
            try:
                from opentelemetry import trace
                current_span = trace.get_current_span()
                if current_span.is_recording():
                    trace_id = format(trace.get_current_span().get_span_context().trace_id, '032x')
                    span_id = format(trace.get_current_span().get_span_context().span_id, '016x')
                    bind_logger_context(trace_id=trace_id, span_id=span_id)
            except (ImportError, Exception):
                pass
                
        start_time = time.time()
        
        # Log request received
        logger.info("http_request_received")
        
        # Process the request
        try:
            response = await call_next(request)
            
            # Add correlation ID to response headers
            response.headers["X-Request-ID"] = request_id
            
            # Log request completion with timing
            duration_ms = (time.time() - start_time) * 1000
            logger.info(
                "http_request_completed",
                status_code=response.status_code,
                duration_ms=round(duration_ms, 2)
            )
            
            return response
        except Exception as e:
            logger.exception("http_request_failed", error=str(e))
            raise
        finally:
            # Clear context vars for next request
            clear_logger_context()
    
    # Health check endpoint - explicitly mark as not requiring auth
    @app.get("/health", tags=["Health"], include_in_schema=True)
    async def health_check() -> Dict[str, Any]:
        """Health check endpoint to verify the API is running."""
        return {
            "status": "ok",
            "version": "0.1.0",
            "service": "whisperserve",
        }
    
    from app.api.routes.jobs import router as jobs_router
    app.include_router(jobs_router, dependencies=[])

    # Setup OpenTelemetry if enabled
    setup_opentelemetry(app, config)
    
    return app
