"""Worker runner for WhisperServe with Temporal integration."""
import asyncio
import uuid
from typing import Optional

import structlog
from temporalio.client import Client as TemporalClient
from temporalio.worker import Worker as TemporalWorker
from temporalio.worker.workflow_sandbox import SandboxedWorkflowRunner, SandboxRestrictions
from temporalio import workflow

from app.utils.config import AppConfig
from app.db.engine import init_db
from app.worker.activities.registry import get_activities
from app.worker.workflows import TranscriptionWorkflow
from app.logging import get_logger
from app.temporal.client import get_temporal_client  # Updated import

with workflow.unsafe.imports_passed_through():
    import pydantic
    import app.worker.models

async def create_worker(
    config: AppConfig, 
    logger: structlog.BoundLogger,
    client: TemporalClient,
    worker_id: Optional[str] = None
) -> TemporalWorker:
    """Create a Temporal worker."""
    # Generate worker ID if not provided
    if not worker_id:
        worker_id = f"worker-{uuid.uuid4()}"
    
    logger = logger.bind(worker_id=worker_id)
    logger.info("creating_temporal_worker")
    
    # Initialize database
    init_db(config.database)
    
    # Get activities from registry
    activities = get_activities()
    
    # Create worker
    worker = TemporalWorker(
        client=client,
        task_queue=config.temporal.task_queue,
        activities=activities,
        workflows=[TranscriptionWorkflow],
        identity=worker_id,
        # TODO: this is bad, figure out how to make sandboxing work
        #       I think this is somewhere in whisperx but I'm not sure about that
        #       and Temporal's error messages are not helpful. I am reasonably
        #       confident (and in saying this I am cursing myself) that we are not
        #       using any nondeterministic functions in our workflow.
        workflow_runner=SandboxedWorkflowRunner(
            restrictions=SandboxRestrictions.default.with_passthrough_all_modules()
        )
    )
    
    logger.info("temporal_worker_created", task_queue=config.temporal.task_queue)
    return worker

async def run_worker(
    worker: TemporalWorker,
    logger: structlog.BoundLogger,
    shutdown_event: asyncio.Event
) -> None:
    """Run a Temporal worker until shutdown is requested."""
    try:
        worker_task = asyncio.create_task(worker.run())
        
        logger.info("temporal_worker_started")
        
        await shutdown_event.wait()
        
        logger.info("shutting_down_worker")
        
        worker_task.cancel()
        try:
            await worker_task
        except asyncio.CancelledError:
            pass
        
        logger.info("worker_shutdown_complete")
    except Exception as e:
        logger.exception("worker_error", error=str(e))

async def create_and_run_worker(
    config: AppConfig,
    logger: structlog.BoundLogger,
    worker_id: Optional[str] = None,
    shutdown_event: Optional[asyncio.Event] = None
) -> None:
    """
    Create and run a worker with a single function call.
    This is the main entry point for CLI to use.
    
    Args:
        config: Application configuration
        logger: Structured logger
        worker_id: Optional ID for the worker
        shutdown_event: Event to signal worker shutdown
    """
    # Create shutdown event if not provided
    if shutdown_event is None:
        shutdown_event = asyncio.Event()
    
    logger.info("starting_worker", worker_id=worker_id or "auto-generated")
    
    try:
        # Use the shared client creation function
        client = await get_temporal_client(config)
        
        # Create worker
        worker = await create_worker(
            config, logger, client, worker_id
        )
        
        # Run worker until shutdown
        await run_worker(worker, logger, shutdown_event)
        
    except Exception as e:
        logger.exception("worker_startup_failed", error=str(e))
        raise
