#!/usr/bin/env python
import asyncio
import logging
import os
import signal
import sys
from typing import Optional

import click
import uvicorn
import structlog
from fastapi import FastAPI

from app.utils.config import load_config, AppConfig
from app.db.engine import init_db, get_engine
from app.worker.backends.mock import MockBackend
from app.worker.backends.whisperx_cpu_backend import WhisperXBackend
from app.worker.processor import JobProcessor
from app.utils.config import BackendType, HardwareAcceleration


# Shared state for signal handling
shutdown_event = asyncio.Event()

# Set up logging
def configure_logging(config):
    """Configure logging based on application configuration."""
    # Set up structlog
    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.processors.add_log_level,
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.JSONRenderer() if config.logging.json_format else structlog.dev.ConsoleRenderer()
        ],
        logger_factory=structlog.stdlib.LoggerFactory(),
    )
    
    # Configure root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(config.logging.level.value)
    
    return structlog.get_logger()

def handle_sigterm(signum, frame):
    """Handle SIGTERM signal by setting shutdown event."""
    print("Received SIGTERM. Initiating graceful shutdown...")
    shutdown_event.set()

# Register signal handlers
signal.signal(signal.SIGTERM, handle_sigterm)
signal.signal(signal.SIGINT, handle_sigterm)


@click.group()
@click.option('--log-level', default=None, help='Override log level from config')
@click.pass_context
def cli(ctx, log_level):
    """WhisperServe: Multi-tenant Speech-to-Text API Service.
    
    This command line tool allows you to run WhisperServe in various modes.
    """
    # Load configuration
    config = load_config()
    
    # Override log level if specified
    if log_level:
        config.logging.level = log_level
    
    # Store config in context for subcommands
    ctx.ensure_object(dict)
    ctx.obj['config'] = config
    
    # Configure logging
    logger = configure_logging(config)
    ctx.obj['logger'] = logger
    
    logger.info("whisperserve_cli_started", version="0.1.0")


@cli.command()
@click.option('--host', help='Override API host from config')
@click.option('--port', type=int, help='Override API port from config')
@click.pass_context
def api(ctx, host, port):
    """Run the API server only."""
    config = ctx.obj['config']
    logger = ctx.obj['logger']
    
    # Override host/port if specified
    if host:
        config.server.host = host
    if port:
        config.server.port = port
    
    logger.info("starting_api_server", 
                host=config.server.host, 
                port=config.server.port)
    
    from app.main import create_app
    
    # Initialize database
    init_db(config.database)
    
    # Create FastAPI app
    app = create_app(config)
    
    # Run with uvicorn
    uvicorn.run(
        app,
        host=config.server.host,
        port=config.server.port,
        log_level=config.logging.level.value.lower()
    )


@cli.command()
@click.option('--worker-id', help='Unique ID for this worker')
@click.pass_context
async def worker(ctx, worker_id):
    """Run the worker process only."""
    config = ctx.obj['config']
    logger = ctx.obj['logger']
    
    # Generate worker ID if not provided
    if not worker_id:
        import uuid
        worker_id = f"worker-{uuid.uuid4()}"
    
    logger.info("starting_worker", worker_id=worker_id)
    
    # Initialize database
    init_db(config.database)
    
    # Create appropriate backend based on configuration
    if config.model.backend == BackendType.MOCK:
        logger.info("using_mock_backend")
        backend = MockBackend(model_size=config.model.model_size)
    elif config.model.backend == BackendType.PYTORCH:
        if config.model.acceleration == HardwareAcceleration.CPU:
            logger.info("using_whisperx_cpu_backend", model_size=config.model.model_size)
            backend = WhisperXBackend(config.model)
        else:
            # TODO: Implement other backends
            logger.error("unsupported_acceleration", acceleration=config.model.acceleration)
            raise ValueError(f"Unsupported acceleration: {config.model.acceleration}")
    else:
        # TODO: Implement other backends
        logger.error("unsupported_backend_type", backend=config.model.backend)
        raise ValueError(f"Unsupported backend type: {config.model.backend}")
    
    # Create job processor
    processor = JobProcessor(
        model_backend=backend,
        server_config=config.server,
        worker_id=worker_id
    )
    
    # Start processor and handle shutdown
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
        
    except Exception as e:
        logger.exception("worker_error", error=str(e))
        sys.exit(1)
    
    logger.info("worker_shutdown_complete")


@cli.command()
@click.option('--host', help='Override API host from config')
@click.option('--port', type=int, help='Override API port from config')
@click.option('--worker-id', help='Unique ID for worker component')
@click.pass_context
async def combined(ctx, host, port, worker_id):
    """Run both API server and worker in the same process."""
    config = ctx.obj['config']
    logger = ctx.obj['logger']
    
    # Override host/port if specified
    if host:
        config.server.host = host
    if port:
        config.server.port = port
    
    # Generate worker ID if not provided
    if not worker_id:
        import uuid
        worker_id = f"worker-{uuid.uuid4()}"
    
    logger.info("starting_combined_mode", 
                host=config.server.host, 
                port=config.server.port,
                worker_id=worker_id)
    
    # Initialize database
    init_db(config.database)
    
    # Create appropriate backend based on configuration
    if config.model.backend == BackendType.MOCK:
        logger.info("using_mock_backend")
        backend = MockBackend(model_size=config.model.model_size)
    elif config.model.backend == BackendType.PYTORCH:
        if config.model.acceleration == HardwareAcceleration.CPU:
            logger.info("using_whisperx_cpu_backend", model_size=config.model.model_size)
            backend = WhisperXBackend(config.model)
        else:
            logger.error("unsupported_acceleration", acceleration=config.model.acceleration)
            raise ValueError(f"Unsupported acceleration: {config.model.acceleration}")
    else:
        logger.error("unsupported_backend_type", backend=config.model.backend)
        raise ValueError(f"Unsupported backend type: {config.model.backend}")
    
    # Create job processor
    processor = JobProcessor(
        model_backend=backend,
        server_config=config.server,
        worker_id=worker_id
    )
    
    # Create FastAPI app
    from app.main import create_app
    app = create_app(config)
    
    # Start processor
    processor_task = asyncio.create_task(processor.start())
    
    # Configure Uvicorn for ASGI server
    config = uvicorn.Config(
        app,
        host=config.server.host,
        port=config.server.port,
        log_level=config.logging.level.value.lower()
    )
    
    # Create server
    server = uvicorn.Server(config)
    
    # Handle shutdown
    async def shutdown():
        logger.info("shutting_down_combined_mode")
        # Stop processor
        await processor.stop()
        # Stop server
        server.should_exit = True
        
    # Register shutdown handler
    asyncio.get_event_loop().add_signal_handler(
        signal.SIGINT,
        lambda: asyncio.create_task(shutdown())
    )
    asyncio.get_event_loop().add_signal_handler(
        signal.SIGTERM,
        lambda: asyncio.create_task(shutdown())
    )
    
    try:
        # Start server (this blocks until server stops)
        await server.serve()
    except Exception as e:
        logger.exception("server_error", error=str(e))
    finally:
        # Ensure processor is stopped if server crashes
        if not processor_task.done():
            await processor.stop()
            await processor_task
        
        logger.info("combined_mode_shutdown_complete")


# Run async commands with asyncio
@cli.command()
@click.argument('subcommand', required=True)
@click.argument('args', nargs=-1)
@click.pass_context
def run_async(ctx, subcommand, args):
    """Run an async subcommand with the event loop."""
    # Create new event loop
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    
    # Get the async command to run
    if subcommand == 'worker':
        cmd = worker
    elif subcommand == 'combined':
        cmd = combined
    else:
        click.echo(f"Unknown async command: {subcommand}")
        sys.exit(1)
    
    try:
        # Run the async command
        loop.run_until_complete(cmd(ctx, *args))
    finally:
        loop.close()


# Main entry point that wraps async commands
def main():
    """Main entry point for the CLI."""
    if len(sys.argv) > 1 and sys.argv[1] in ['worker', 'combined']:
        # For async commands, use run_async wrapper
        sys.argv[0] = sys.argv[0] + " run_async"
        sys.argv.insert(1, "run_async")
    
    cli()


if __name__ == "__main__":
    main()
