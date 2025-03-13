"""API server runner for WhisperServe."""
import structlog
import uvicorn
from fastapi import FastAPI
from typing import Tuple, Optional

from app.utils.config import AppConfig
from app.db.engine import init_db
from app.utils.migrations import run_migrations

def create_api_app(config: AppConfig) -> FastAPI:
    """Create and configure the FastAPI application."""
    from app.api.server import create_app

    # Run database migrations
    run_migrations()
    
    # Initialize database
    init_db(config.database, config.telemetry)
    
    # Create FastAPI app
    return create_app(config)

def _prepare_server(
    config: AppConfig, 
    logger: structlog.BoundLogger, 
    host: Optional[str] = None, 
    port: Optional[int] = None
) -> Tuple[FastAPI, uvicorn.Config]:
    """
    Prepare server components for running or creating a server.
    
    Args:
        config: Application configuration
        logger: Logger instance
        host: Override host from config
        port: Override port from config
        
    Returns:
        Tuple of (FastAPI app, uvicorn.Config)
    """
    # Override host/port if specified
    server_host = host if host is not None else config.server.host
    server_port = port if port is not None else config.server.port
    
    logger.info("preparing_api_server", 
                host=server_host, 
                port=server_port)
    
    # Create the app
    app = create_api_app(config)
    
    # Create uvicorn configuration
    uvicorn_config = uvicorn.Config(
        app,
        host=server_host,
        port=server_port,
        log_level=config.logging.level.value.lower()
    )
    
    return app, uvicorn_config

def run_api_server(
    config: AppConfig, 
    logger: structlog.BoundLogger, 
    host: Optional[str] = None, 
    port: Optional[int] = None
) -> None:
    """Run the API server with the given configuration."""
    app, uvicorn_config = _prepare_server(config, logger, host, port)
    
    logger.info("starting_api_server", 
                host=uvicorn_config.host, 
                port=uvicorn_config.port)
    
    # Run with uvicorn (blocking call)
    uvicorn.run(
        app,
        host=uvicorn_config.host,
        port=uvicorn_config.port,
        log_level=uvicorn_config.log_level,
    )

async def create_server(
    config: AppConfig,
    logger: structlog.BoundLogger,
    host: Optional[str] = None,
    port: Optional[int] = None
) -> uvicorn.Server:
    """Create a uvicorn server instance without starting it."""
    _, uvicorn_config = _prepare_server(config, logger, host, port)
    
    logger.info("creating_api_server", 
                host=uvicorn_config.host, 
                port=uvicorn_config.port)
    
    # Return the server without starting it (for CLI's `combined` mode)
    return uvicorn.Server(uvicorn_config)
