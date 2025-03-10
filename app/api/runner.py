"""API server runner for WhisperServe."""
import structlog
import uvicorn
from fastapi import FastAPI

from app.utils.config import AppConfig
from app.db.engine import init_db

def create_api_app(config: AppConfig) -> FastAPI:
    """Create and configure the FastAPI application."""
    from app.api.server import create_app

    # Initialize database
    init_db(config.database)
    
    # Create FastAPI app
    return create_app(config)

def run_api_server(
    config: AppConfig, 
    logger: structlog.BoundLogger, 
    host: str | None = None, 
    port: int | None = None
) -> None:
    """Run the API server with the given configuration."""
    # Override host/port if specified
    if host:
        config.server.host = host
    if port:
        config.server.port = port
    
    logger.info("starting_api_server", 
                host=config.server.host, 
                port=config.server.port)
    
    # Create the app
    app = create_api_app(config)
    
    # Run with uvicorn
    uvicorn.run(
        app,
        host=config.server.host,
        port=config.server.port,
        log_level=config.logging.level.value.lower()
    )

async def create_server(
    config: AppConfig,
    logger: structlog.BoundLogger,
    host: str | None = None,
    port: int | None = None
) -> uvicorn.Server:
    """Create a uvicorn server instance without starting it."""
    # Override host/port if specified
    if host:
        config.server.host = host
    if port:
        config.server.port = port
    
    logger.info("creating_api_server", 
                host=config.server.host, 
                port=config.server.port)
    
    # Create the app
    app = create_api_app(config)
    
    # Configure Uvicorn for ASGI server
    uvicorn_config = uvicorn.Config(
        app,
        host=config.server.host,
        port=config.server.port,
        log_level=config.logging.level.value.lower()
    )
    
    # Return the server without starting it
    return uvicorn.Server(uvicorn_config)