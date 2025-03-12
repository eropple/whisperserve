#!/usr/bin/env python
import asyncio
import logging
import signal
import sys
from typing import Optional, TypedDict, Dict, Any

import click
import structlog

from app.utils.config import load_config, AppConfig, LogLevel
from app.api.runner import run_api_server, create_server
from app.worker.runner import create_and_run_worker, create_worker, run_worker
from app.logging import configure_logging

class ClickContext(TypedDict):
    config: AppConfig
    logger: structlog.BoundLogger

# Shared state for signal handling
shutdown_event = asyncio.Event()

def handle_sigterm(signum: int, frame: Any) -> None:
    """Handle SIGTERM signal by setting shutdown event."""
    print("Received SIGTERM. Initiating graceful shutdown...")
    shutdown_event.set()

# Register signal handlers
signal.signal(signal.SIGTERM, handle_sigterm)
signal.signal(signal.SIGINT, handle_sigterm)


@click.group()
@click.option('--log-level', default=None, help='Override log level from config')
@click.pass_context
def cli(ctx: click.Context, log_level: Optional[str]) -> None:
    """WhisperServe: Multi-tenant Speech-to-Text API Service.
    
    This command line tool allows you to run WhisperServe in various modes.
    """
    # Load configuration
    config = load_config()
    
    # Override log level if specified
    if log_level:
        try:
            # Convert string to LogLevel enum
            config.logging.level = LogLevel(log_level.upper())
        except ValueError:
            valid_levels = [level.value for level in LogLevel]
            print(f"Invalid log level: {log_level}. Valid options are: {', '.join(valid_levels)}")
            sys.exit(1)
    
    # Store config in context for subcommands
    ctx.ensure_object(dict)
    ctx.obj = {'config': config}
    
    # Configure logging
    logger = configure_logging(config)
    ctx.obj['logger'] = logger
    
    logger.info("whisperserve_cli_started", version="0.1.0")


@cli.command()
@click.option('--host', help='Override API host from config')
@click.option('--port', type=int, help='Override API port from config')
@click.pass_context
def api(ctx: click.Context, host: Optional[str], port: Optional[int]) -> None:
    """Run the API server only."""
    obj: Dict[str, Any] = ctx.obj
    config: AppConfig = obj['config']
    logger: structlog.BoundLogger = obj['logger']
    
    # Run API server (this will block until server stops)
    run_api_server(config, logger, host, port)


@cli.command()
@click.option('--worker-id', help='Unique ID for this worker')
@click.pass_context
def worker(ctx: click.Context, worker_id: Optional[str]):
    """Run the worker process only."""
    # Get config and logger from context
    config = ctx.obj['config']
    logger = ctx.obj['logger']
    
    # Create event loop
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    
    # Create shutdown event
    shutdown_event = asyncio.Event()
    
    # Set up signal handlers
    def signal_handler():
        logger.info("Received shutdown signal")
        shutdown_event.set()
    
    # Register signals
    for sig in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(sig, signal_handler)
    
    try:
        # Import here to avoid circular imports
        from app.worker.runner import create_and_run_worker
        
        # Run worker until shutdown
        loop.run_until_complete(
            create_and_run_worker(config, logger, worker_id, shutdown_event)
        )
    except Exception as e:
        logger.exception("worker_error", error=str(e))
        sys.exit(1)
    finally:
        loop.close()



@cli.command()
@click.option('--host', help='Override API host from config')
@click.option('--port', type=int, help='Override API port from config')
@click.option('--worker-id', help='Unique ID for worker component')
@click.pass_context
def combined(ctx: click.Context, host: Optional[str], port: Optional[int], worker_id: Optional[str]):
    """Run both API server and worker in the same process."""
    # Get config and logger from context
    config = ctx.obj['config']
    logger = ctx.obj['logger']
    
    # Create event loop
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    
    # Create shutdown event
    shutdown_event = asyncio.Event()
    
    try:
        # Import dependencies here to avoid circular imports
        from app.worker.runner import create_and_run_worker
        from app.api.runner import create_server
        
        # Create and start tasks
        async def start_combined():
            # Create API server
            server = await create_server(config, logger, host, port)
            
            # Start worker in background
            worker_task = asyncio.create_task(
                create_and_run_worker(config, logger, worker_id, shutdown_event)
            )
            
            # Set up graceful shutdown
            def signal_handler():
                logger.info("Received shutdown signal")
                shutdown_event.set()
                server.should_exit = True
            
            # Register signals in the running loop
            for sig in (signal.SIGINT, signal.SIGTERM):
                loop.add_signal_handler(sig, signal_handler)
            
            try:
                # Run server (blocks until exit)
                await server.serve()
            finally:
                # Ensure worker task is stopped
                if not worker_task.done():
                    await asyncio.wait_for(worker_task, timeout=10.0)
                logger.info("combined_mode_shutdown_complete")
        
        # Run the combined mode
        loop.run_until_complete(start_combined())
            
    except Exception as e:
        logger.exception("combined_mode_error", error=str(e))
        sys.exit(1)
    finally:
        loop.close()

@cli.command()
@click.argument('audio_file', type=click.Path(exists=True))
@click.option('--language', help='Override language detection')
@click.option('--model-size', help='Override model size from config')
@click.pass_context
def transcribe(ctx: click.Context, audio_file: str, language: Optional[str] = None, 
                model_size: Optional[str] = None):
    """Transcribe an audio file using the configured backend and output as JSON."""
    import json
    from app.worker.backends.factory import create_backend
    
    # Get config and logger from context
    config = ctx.obj['config']
    logger = ctx.obj['logger']
    
    # Override model size if specified
    if model_size:
        config.model.model_size = model_size
    
    # Create event loop
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    
    # Define the async function that will do the work
    async def run_transcription():
        logger.info("initializing_backend")
        
        # Create backend from factory
        backend = create_backend(config, logger)
        
        # Initialize backend
        if not await backend.initialize():
            logger.error("backend_initialization_failed")
            sys.exit(1)
        
        try:
            logger.info("starting_transcription", file=audio_file)
            
            # Set options
            options = {"processing_mode": "downmix"}
            if language:
                options["language"] = language
            
            # Run transcription
            result = await backend.transcribe(audio_file, options)
            
            # Print result as JSON
            print(json.dumps(result.to_dict(), indent=2))
            
        finally:
            await backend.shutdown()
    
    try:
        # Run the async function
        loop.run_until_complete(run_transcription())
    except Exception as e:
        logger.exception("transcription_failed", error=str(e))
        sys.exit(1)
    finally:
        loop.close()



def main():
    """Main entry point for the CLI."""
    cli()


if __name__ == "__main__":
    main()