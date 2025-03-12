"""Logging configuration for WhisperServe.

This module provides centralized logging configuration for both structlog and
the standard Python logging system, ensuring consistent log formats throughout
the application.
"""
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
        formatter = structlog.processors.JSONRenderer()
    else:
        formatter = structlog.dev.ConsoleRenderer(colors=True)
    
    # Common processors for both structlog and stdlib
    shared_processors = [
        structlog.contextvars.merge_contextvars,
        structlog.processors.add_log_level,
        structlog.processors.TimeStamper(fmt="iso"),  # Add timestamp to all logs
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
    ]
    
    # Processors for structlog
    structlog_processors = shared_processors + [
        # Wraps for stdlib formatter integration
        structlog.stdlib.ProcessorFormatter.wrap_for_formatter,
    ]
    
    # Processors for stdlib logging records
    stdlib_processors = shared_processors + [
        structlog.stdlib.add_logger_name,  # Add logger name only for stdlib logs
    ]
    
    # Set up standard logging
    handler = logging.StreamHandler()
    
    # Create formatter for stdlib logging
    formatter_processor = structlog.stdlib.ProcessorFormatter(
        processor=formatter,
        foreign_pre_chain=stdlib_processors,  # Use stdlib chain
    )
    
    # Apply formatter to handler
    handler.setFormatter(formatter_processor)
    
    # Get log level as integer
    log_level = get_log_level_from_string(config.logging.level.value)
    
    # Configure root logger
    root_logger = logging.getLogger()
    root_logger.handlers.clear()
    root_logger.addHandler(handler)
    root_logger.setLevel(log_level)
    
    # Configure structlog AFTER stdlib logging is set up
    structlog.configure(
        processors=structlog_processors,  # Use structlog chain
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.stdlib.BoundLogger,
        cache_logger_on_first_use=True,
    )
    
    # Create and return a logger
    logger = structlog.get_logger()
    logger.info("logging_configured", level=config.logging.level.value)
    
    return logger


def get_logger(name: Optional[str] = None) -> structlog.BoundLogger:
    """Get a structlog logger.
    
    This is a convenience wrapper around structlog.get_logger() that ensures
    consistent logger creation throughout the application.
    
    Args:
        name: Optional name for the logger (typically the module name)
        
    Returns:
        A configured structlog logger
    """
    return structlog.get_logger(name)

def bind_logger_context(**kwargs) -> None:
    """Bind key-value pairs to the context of all future logs.
    
    Args:
        **kwargs: Key-value pairs to add to the log context
    """
    structlog.contextvars.bind_contextvars(**kwargs)

def clear_logger_context() -> None:
    """Clear all values from the contextvars-based logging context."""
    structlog.contextvars.clear_contextvars()
