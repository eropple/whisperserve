"""S3 client utilities."""
import boto3
from botocore.client import Config, BaseClient
import structlog

from app.utils.config import S3Config, OpenTelemetryConfig

# Configure logger
logger = structlog.get_logger(__name__)

def create_s3_client(config: S3Config, telemetry_config: OpenTelemetryConfig) -> BaseClient:
    """
    Create and configure an S3 client with OpenTelemetry instrumentation.
    
    Args:
        config: S3 configuration
        telemetry_config: Telemetry configuration for OTEL setup
        
    Returns:
        BaseClient: Configured S3 client
    """
    client = boto3.client(
        's3',
        endpoint_url=config.endpoint_url,
        aws_access_key_id=config.access_key,
        aws_secret_access_key=config.secret_key,
        config=Config(signature_version='s3v4'),
        use_ssl=config.ssl,
    )
    
    # Setup OpenTelemetry for Boto if enabled
    if telemetry_config.enabled:
        try:
            from opentelemetry.instrumentation.boto import BotoInstrumentor
            
            # Instrument Boto
            BotoInstrumentor().instrument()
            logger.info("boto_opentelemetry_initialized")
        except ImportError:
            logger.warning("boto_instrumentation_missing", 
                           message="Boto OTEL instrumentation not installed")
        except Exception as e:
            logger.exception("boto_instrumentation_failed", error=str(e))
    
    return client
