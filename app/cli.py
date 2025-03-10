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
from app.worker.runner import create_worker, run_worker

# Define a type for our Click context object
class ClickContext(TypedDict):
    config: AppConfig
    logger: structlog.BoundLogger

# Shared state for signal handling
shutdown_event = asyncio.Event()

# Set up logging
def configure_logging(config: AppConfig) -> structlog.BoundLogger:
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
async def worker(ctx: click.Context, worker_id: Optional[str]) -> None:
    """Run the worker process only."""
    obj: Dict[str, Any] = ctx.obj
    config: AppConfig = obj['config']
    logger: structlog.BoundLogger = obj['logger']
    
    # Create the worker
    processor, _ = create_worker(config, logger, worker_id)
    
    # Run the worker until shutdown
    try:
        await run_worker(processor, logger, shutdown_event)
    except Exception as e:
        logger.exception("worker_run_error", error=str(e))
        sys.exit(1)


@cli.command()
@click.option('--host', help='Override API host from config')
@click.option('--port', type=int, help='Override API port from config')
@click.option('--worker-id', help='Unique ID for worker component')
@click.pass_context
async def combined(ctx: click.Context, host: Optional[str], port: Optional[int], worker_id: Optional[str]) -> None:
    """Run both API server and worker in the same process."""
    obj: Dict[str, Any] = ctx.obj
    config: AppConfig = obj['config']
    logger: structlog.BoundLogger = obj['logger']
    
    logger.info("starting_combined_mode", 
                host=host or config.server.host, 
                port=port or config.server.port,
                worker_id=worker_id)
    
    # Create worker
    processor, _ = create_worker(config, logger, worker_id)
    
    # Create API server (but don't start it yet)
    server = await create_server(config, logger, host, port)
    
    # Start processor
    processor_task = asyncio.create_task(processor.start())
    
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
def run_async(ctx: click.Context, subcommand: str, args: tuple) -> None:
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
def main() -> None:
    """Main entry point for the CLI."""
    if len(sys.argv) > 1 and sys.argv[1] in ['worker', 'combined']:
        # For async commands, use run_async wrapper
        sys.argv[0] = sys.argv[0] + " run_async"
        sys.argv.insert(1, "run_async")
    
    cli()


if __name__ == "__main__":
    main()