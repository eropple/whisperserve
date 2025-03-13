"""Logging configuration for WhisperServe."""
import logging
import sys
from typing import List, Optional, Any, Dict

import structlog
from structlog.types import Processor

from app.utils.config import AppConfig, LogLevel

def get_log_level_from_string(level_str: str) -> int:
    """Convert string log level to logging module constant."""
    level_map = {
        "DEBUG": logging.DEBUG,
        "INFO": logging.INFO,
        "WARNING": logging.WARNING,
        "ERROR": logging.ERROR,
        "CRITICAL": logging.CRITICAL
    }
    return level_map.get(level_str.upper(), logging.INFO)

def configure_logging(config: AppConfig) -> structlog.BoundLogger:
    """Configure logging based on application configuration."""
    # Define renderer based on config
    if config.logging.json_format:
        renderer = structlog.processors.JSONRenderer()
    else:
        renderer = structlog.dev.ConsoleRenderer(colors=True)
    
    # Get log level as integer
    log_level = get_log_level_from_string(config.logging.level.value)
    
    # Configure structlog with basic processors
    structlog.configure(
        processors=[
            structlog.stdlib.filter_by_level,
            structlog.stdlib.add_logger_name,
            structlog.stdlib.add_log_level,
            structlog.stdlib.PositionalArgumentsFormatter(),
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.contextvars.merge_contextvars,
            structlog.processors.StackInfoRenderer(),
            structlog.processors.format_exc_info,
            structlog.processors.UnicodeDecoder(),
            renderer,
        ],
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.stdlib.BoundLogger,
        cache_logger_on_first_use=True,
    )
    
    # Set up basic logging for standard library loggers
    handler = logging.StreamHandler()
    handler.setFormatter(logging.Formatter("%(message)s"))
    
    # Configure root logger
    root_logger = logging.getLogger()
    root_logger.handlers = [handler]
    root_logger.setLevel(log_level)
    
    # Create our logger
    logger = structlog.get_logger()
    logger.info("logging_configured", level=config.logging.level.value)
    
    return logger

def get_logger(name: Optional[str] = None) -> structlog.BoundLogger:
    """Get a structlog logger."""
    return structlog.get_logger(name)

def bind_logger_context(**kwargs) -> None:
    """Bind key-value pairs to the context of all future logs."""
    structlog.contextvars.bind_contextvars(**kwargs)

def clear_logger_context() -> None:
    """Clear all values from the contextvars-based logging context."""
    structlog.contextvars.clear_contextvars()
