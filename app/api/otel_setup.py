from fastapi import FastAPI
from app.logging import get_logger
from app.utils.config import AppConfig
from app.utils.otel import setup_tracer_provider

logger = get_logger(__name__)

def setup_opentelemetry(app: FastAPI, config: AppConfig) -> None:
    """Set up OpenTelemetry instrumentation if enabled in config."""
    tracer_provider = setup_tracer_provider(config)
    if not tracer_provider:
        return
    
    try:
        # Import FastAPI instrumentation
        from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
        
        # Instrument FastAPI
        FastAPIInstrumentor.instrument_app(
            app,
            tracer_provider=tracer_provider,
        )
        
        logger.info("fastapi_opentelemetry_initialized", 
                    endpoint=config.telemetry.endpoint, 
                    service_name=config.telemetry.service_name)
    except ImportError:
        logger.warning("fastapi_instrumentation_missing", 
                        message="FastAPI OTEL instrumentation not installed")
    except Exception as e:
        logger.exception("fastapi_instrumentation_failed", error=str(e))
