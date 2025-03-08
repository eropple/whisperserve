from typing import Dict, Any, AsyncGenerator
import asyncio
from contextlib import asynccontextmanager

from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, AsyncEngine, async_sessionmaker
from sqlalchemy.orm import sessionmaker

from app.utils.config import DatabaseConfig

# Global engine instance
_engine: AsyncEngine | None = None

def init_db(config: DatabaseConfig) -> AsyncEngine:
    """Initialize database engine with the provided configuration."""
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
    
    return _engine

def get_engine() -> AsyncEngine:
    """Get the database engine instance."""
    if _engine is None:
        raise RuntimeError("Database engine not initialized. Call init_db first.")
    return _engine

@asynccontextmanager
async def get_db_session() -> AsyncGenerator[AsyncSession, None]:
    """Provide a database session within a context manager."""
    if _engine is None:
        raise RuntimeError("Database engine not initialized. Call init_db first.")
    
    # Create the session factory here to ensure it has the latest engine
    session_factory = async_sessionmaker(bind=_engine, expire_on_commit=False)
    
    # This will properly return an AsyncSession
    session = session_factory()
    try:
        yield session
        await session.commit()
    except Exception:
        await session.rollback()
        raise
    finally:
        await session.close()
