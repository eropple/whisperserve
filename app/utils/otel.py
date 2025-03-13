"""OpenTelemetry utility functions."""
import structlog
from typing import Optional

from app.utils.config import AppConfig
from opentelemetry.sdk.trace import TracerProvider

# Configure logger
logger = structlog.get_logger(__name__)

def setup_tracer_provider(config: AppConfig) -> Optional[TracerProvider]:
    """
    Set up and configure an OpenTelemetry TracerProvider.
    
    Args:
        config: Application configuration
        
    Returns:
        TracerProvider if successful, None otherwise
    """
    if not config.telemetry.enabled or not config.telemetry.endpoint:
        logger.debug("opentelemetry_disabled")
        return None
    
    try:
        # Import OTEL libraries
        from opentelemetry import trace
        from opentelemetry.sdk.trace import TracerProvider
        from opentelemetry.sdk.resources import Resource
        from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
        from opentelemetry.sdk.trace.export import BatchSpanProcessor
        
        # Set up tracer provider with service name
        resource = Resource.create({"service.name": config.telemetry.service_name})
        tracer_provider = TracerProvider(resource=resource)
        
        # Configure OTLP exporter
        otlp_exporter = OTLPSpanExporter(
            endpoint=config.telemetry.endpoint,
            insecure=config.telemetry.insecure
        )
        
        # Add span processor to tracer provider
        span_processor = BatchSpanProcessor(otlp_exporter)
        tracer_provider.add_span_processor(span_processor)
        
        # Set as global tracer provider
        trace.set_tracer_provider(tracer_provider)
        
        logger.debug("tracer_provider_initialized", 
                    endpoint=config.telemetry.endpoint, 
                    service_name=config.telemetry.service_name)
        
        return tracer_provider
    except ImportError:
        logger.warning("opentelemetry_modules_missing", 
                      message="OpenTelemetry enabled but required modules not installed")
    except Exception as e:
        logger.exception("tracer_provider_initialization_failed", error=str(e))
    
    return None
