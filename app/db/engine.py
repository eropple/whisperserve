from typing import Dict, Any, AsyncGenerator, Optional
from contextlib import asynccontextmanager

from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, AsyncEngine, async_sessionmaker
from sqlalchemy.orm import sessionmaker

from app.utils.config import DatabaseConfig, OpenTelemetryConfig
from app.logging import get_logger

# Configure logger
logger = get_logger(__name__)

# Global engine instance
_engine: AsyncEngine | None = None

def init_db(config: DatabaseConfig, telemetry_config: Optional[OpenTelemetryConfig] = None) -> AsyncEngine:
    """
    Initialize database engine with the provided configuration.
    
    Args:
        config: Database configuration
        telemetry_config: Optional telemetry configuration for OTEL setup
        
    Returns:
        AsyncEngine: Initialized SQLAlchemy engine
    """
    global _engine
    
    # Create async engine
    connection_args: Dict[str, Any] = {
        "echo": config.echo_queries,
    }
    
    # Convert regular PostgreSQL DSN to async DSN
    dsn = str(config.dsn)
    if dsn.startswith("postgresql://"):
        dsn = dsn.replace("postgresql://", "postgresql+asyncpg://")
    
    _engine = create_async_engine(
        dsn,
        pool_size=config.min_connections,
        max_overflow=config.max_connections - config.min_connections,
        **connection_args
    )
    
    # Setup OpenTelemetry for SQLAlchemy if enabled
    if telemetry_config and telemetry_config.enabled:
        try:
            from opentelemetry.instrumentation.sqlalchemy import SQLAlchemyInstrumentor
            
            # Instrument SQLAlchemy
            SQLAlchemyInstrumentor().instrument(
                engine=_engine.sync_engine  # Use the underlying sync engine for instrumentation
            )
            logger.info("sqlalchemy_opentelemetry_initialized")
        except ImportError:
            logger.warning("sqlalchemy_instrumentation_missing", 
                            message="SQLAlchemy OTEL instrumentation not installed")
        except Exception as e:
            logger.exception("sqlalchemy_instrumentation_failed", error=str(e))
    
    return _engine

def get_engine() -> AsyncEngine:
    """Get the database engine instance."""
    if _engine is None:
        raise RuntimeError("Database engine not initialized. Call init_db first.")
    return _engine

@asynccontextmanager
async def get_db_session() -> AsyncGenerator[AsyncSession, None]:
    """Provide a database session within a context manager."""
    global _engine
    if _engine is None:
        from app.utils.config import load_config
        config = load_config()
        init_db(config.database, telemetry_config=config.telemetry)
    
    session_factory = async_sessionmaker(bind=_engine, expire_on_commit=False)
    
    session = session_factory()
    try:
        yield session
        await session.commit()
    except Exception:
        await session.rollback()
        raise
    finally:
        await session.close()
