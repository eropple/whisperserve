"""Factory for creating model backends."""
import structlog

from app.utils.config import AppConfig, HardwareAcceleration
from app.worker.backends.base import ModelBackend
from app.worker.backends.mock import MockBackend
from app.worker.backends.whisperx_cpu_backend import WhisperXCPUBackend

def create_backend(config: AppConfig, logger: structlog.BoundLogger) -> ModelBackend:
    """Create and initialize the appropriate model backend based on configuration."""
    # Create appropriate backend based on configuration
    if config.model.acceleration == HardwareAcceleration.MOCK:
        logger.info("using_mock_backend")
        return MockBackend(model_size=config.model.model_size)
    elif config.model.acceleration == HardwareAcceleration.CPU:
        logger.info("using_whisperx_cpu_backend", model_size=config.model.model_size)
        return WhisperXCPUBackend(config.model)
    else:
        # TODO: Implement other backends
        logger.error("unsupported_acceleration", acceleration=config.model.acceleration)
        raise ValueError(f"Unsupported acceleration: {config.model.acceleration}")
