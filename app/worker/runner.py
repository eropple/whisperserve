"""Worker runner for WhisperServe."""
import asyncio
import uuid
from typing import Optional, Tuple

import structlog

from app.utils.config import AppConfig, HardwareAcceleration
from app.db.engine import init_db
from app.worker.backends.base import ModelBackend
from app.worker.backends.mock import MockBackend
from app.worker.backends.whisperx_cpu_backend import WhisperXCPUBackend
from app.worker.processor import JobProcessor

def create_backend(config: AppConfig, logger: structlog.BoundLogger) -> ModelBackend:
    """Create and initialize the appropriate model backend based on configuration."""
    # Create appropriate backend based on configuration
    if config.model.acceleration == HardwareAcceleration.MOCK:
        logger.info("using_mock_backend")
        backend = MockBackend(model_size=config.model.model_size)
    elif config.model.acceleration == HardwareAcceleration.CPU:
        logger.info("using_whisperx_cpu_backend", model_size=config.model.model_size)
        backend = WhisperXCPUBackend(config.model)
    else:
        # TODO: Implement other backends
        logger.error("unsupported_acceleration", acceleration=config.model.acceleration)
        raise ValueError(f"Unsupported acceleration: {config.model.acceleration}")
    
    return backend

def create_worker(
    config: AppConfig, 
    logger: structlog.BoundLogger,
    worker_id: Optional[str] = None
) -> Tuple[JobProcessor, ModelBackend]:
    """Create and initialize a worker processor."""
    # Initialize database
    init_db(config.database)
    
    # Generate worker ID if not provided
    if not worker_id:
        worker_id = f"worker-{uuid.uuid4()}"
    
    logger.info("creating_worker", worker_id=worker_id)
    
    # Create backend
    backend = create_backend(config, logger)
    
    # Create job processor
    processor = JobProcessor(
        model_backend=backend,
        server_config=config.server,
        worker_id=worker_id
    )
    
    return processor, backend

async def run_worker(
    processor: JobProcessor,
    logger: structlog.BoundLogger,
    shutdown_event: asyncio.Event
) -> None:
    """Run a worker processor until shutdown is requested."""
    try:
        # Create task for the processor
        processor_task = asyncio.create_task(processor.start())
        
        # Wait for shutdown signal
        await shutdown_event.wait()
        
        # Stop processor gracefully
        logger.info("shutting_down_worker")
        await processor.stop()
        
        # Wait for processor to complete shutdown
        await processor_task
        
        logger.info("worker_shutdown_complete")
    except Exception as e:
        logger.exception("worker_error", error=str(e))
        raise