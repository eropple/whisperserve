"""Shared Temporal client functionality for both API and worker components."""
from temporalio.client import Client as TemporalClient
from temporalio.contrib.pydantic import pydantic_data_converter

from app.utils.config import AppConfig
from app.logging import get_logger

logger = get_logger(__name__)

async def get_temporal_client(config: AppConfig) -> TemporalClient:
    """
    Create and connect to the Temporal server.
    
    This function is used by both the API server and worker processes
    to ensure consistent client configuration.
    
    Args:
        config: Application configuration
        
    Returns:
        TemporalClient: Connected Temporal client
    """
    logger.info("connecting_to_temporal", 
                namespace=config.temporal.namespace, 
                server=config.temporal.server_address)
    
    # Connect to Temporal server with Pydantic data converter
    client = await TemporalClient.connect(
        config.temporal.server_address,
        namespace=config.temporal.namespace,
        data_converter=pydantic_data_converter
    )
    
    logger.info("temporal_client_connected")
    return client