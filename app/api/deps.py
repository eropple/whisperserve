"""Dependency injection utilities for FastAPI."""
from typing import Annotated, AsyncGenerator, Optional
import uuid
from sqlalchemy.ext.asyncio import AsyncSession
from fastapi import Depends, Request, Header, HTTPException
from temporalio.client import Client as TemporalClient

from app.utils.config import AppConfig, load_config
from app.db.engine import get_db_session
from app.logging import get_logger
from app.temporal.client import get_temporal_client
from app.utils.jwt_utils import extract_tenant_id

# Create a logger instance for this module
logger = get_logger(__name__)

async def get_config() -> AppConfig:
    """
    Dependency to provide application configuration.
    
    Returns:
        AppConfig: The loaded application configuration
    """
    return load_config()

async def get_db(
    config: Annotated[AppConfig, Depends(get_config)]
) -> AsyncGenerator[AsyncSession, None]:
    """
    Dependency to provide database session.
    
    Args:
        config: Application configuration
        
    Yields:
        AsyncSession: SQLAlchemy async session
    """
    async with get_db_session() as session:
        yield session

async def get_client(
    config: Annotated[AppConfig, Depends(get_config)]
) -> TemporalClient:
    """
    Dependency to provide Temporal client.
    
    Args:
        config: Application configuration
        
    Returns:
        TemporalClient: Configured Temporal client
    """
    return await get_temporal_client(config)

async def get_tenant_id(
    authorization: Annotated[str, Header()],
    config: Annotated[AppConfig, Depends(get_config)]
) -> str:
    """
    Extract and validate tenant ID from JWT token.
    
    Args:
        authorization: Authorization header containing JWT
        config: Application configuration
        
    Returns:
        str: Validated tenant ID
        
    Raises:
        HTTPException: If token is invalid or missing tenant ID
    """
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing or invalid authorization header")
    
    token = authorization.replace("Bearer ", "")
    
    try:
        tenant_id = extract_tenant_id(token, config, raise_exceptions=True)
        if not tenant_id:
            raise HTTPException(
                status_code=403, 
                detail=f"Token missing required claim: {config.jwt.tenant_claim}"
            )
        
        return tenant_id
    except ValueError as e:
        logger.warning("jwt_validation_failed", error=str(e))
        raise HTTPException(status_code=401, detail=str(e))
    except Exception as e:
        logger.exception("tenant_id_extraction_error", error=str(e))
        raise HTTPException(status_code=500, detail="Authentication error")

async def get_request_logger(request: Request) -> AsyncGenerator[get_logger.BoundLogger, None]:
    """
    Get a logger instance with request context.
    
    Args:
        request: FastAPI request object
        
    Yields:
        BoundLogger: Logger with request context
    """
    # Generate unique request ID if not already present
    request_id = request.headers.get("X-Request-ID") or str(uuid.uuid4())
    
    # Create bound logger with request context
    log = get_logger().bind(
        request_id=request_id,
        path=request.url.path,
        method=request.method,
        client_ip=request.client.host if request.client else None
    )
    
    yield log
