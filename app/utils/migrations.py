"""Utility functions for database migrations."""
import os
import logging
from alembic.config import Config as AlembicConfig
from alembic import command
from app.utils.config import load_config
from app.logging import get_logger

# Get structured logger for migrations
logger = get_logger(__name__)

def run_migrations():
    """
    Run all pending database migrations.
    
    This is designed to be called during application startup to ensure 
    the database schema is up to date.
    
    Raises:
        Exception: If migrations fail for any reason
    """
    logger.info("Starting database migrations")
    
    # Get project root directory
    app_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    project_dir = os.path.dirname(app_dir)
    
    # Create Alembic configuration and point it to alembic.ini
    alembic_cfg = AlembicConfig(os.path.join(project_dir, "alembic.ini"))
    
    # Override sqlalchemy.url with current database DSN
    # Convert asyncpg URL to synchronous URL for Alembic
    app_config = load_config()
    db_url = str(app_config.database.dsn)
    if db_url.startswith("postgresql+asyncpg://"):
        db_url = db_url.replace("postgresql+asyncpg://", "postgresql://")
        
    alembic_cfg.set_main_option("sqlalchemy.url", db_url)
    
    # Run migrations - let any exceptions propagate
    logger.info(f"Running database migrations using {db_url}")
    command.upgrade(alembic_cfg, "head")
    logger.info("Database migrations completed successfully")
