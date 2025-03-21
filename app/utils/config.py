from enum import Enum
from typing import Dict, List, Optional, Any, Type, TypeVar, cast

from pydantic import BaseModel, Field, PostgresDsn, field_validator, model_validator

from app.utils.jwt_config import JWTConfig, load_jwt_config
from app.utils.config_utils import (
    get_env_str, get_env_value, get_env_bool, get_env_int, get_env_float
)

# Type definitions
T = TypeVar('T', bound=BaseModel)

class LogLevel(str, Enum):
    DEBUG = "DEBUG"
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"
    CRITICAL = "CRITICAL"


class HardwareAcceleration(str, Enum):
    CPU = "cpu"
    CUDA = "cuda"
    ROCM = "rocm"
    METAL = "metal"
    MOCK = "mock"


class ModelConfig(BaseModel):
    acceleration: HardwareAcceleration = Field(default=HardwareAcceleration.CPU, description="Hardware acceleration type")
    model_size: str = Field(default="base", description="Model size (tiny, base, small, medium, large)")
    model_path: Optional[str] = Field(default=None, description="Custom path to model files")
    cache_dir: str = Field(default="/tmp/whisperserve/models", description="Directory to cache model files")


class DatabaseConfig(BaseModel):
    dsn: PostgresDsn = Field(..., description="PostgreSQL connection string")
    min_connections: int = Field(default=5, description="Minimum number of connections in the pool")
    max_connections: int = Field(default=20, description="Maximum number of connections in the pool")
    echo_queries: bool = Field(default=False, description="Enable SQL query logging")


class LoggingConfig(BaseModel):
    level: LogLevel = Field(default=LogLevel.INFO, description="Logging level")
    json_format: bool = Field(default=True, description="Use JSON format for logs")


class OpenTelemetryConfig(BaseModel):
    enabled: bool = Field(default=False, description="Enable OpenTelemetry integration")
    endpoint: Optional[str] = Field(default=None, description="OpenTelemetry collector endpoint")
    service_name: str = Field(default="whisperserve", description="Service name for OpenTelemetry")
    insecure: bool = Field(default=False, description="Disable TLS for OpenTelemetry collector connection")


class S3BucketsConfig(BaseModel):
    """Configuration for S3 buckets used by the application."""
    work_area: str = Field(..., description="Bucket for temporary work files during transcription")


class S3Config(BaseModel):
    """Configuration for S3 compatible storage."""
    endpoint: str = Field(..., description="S3 endpoint without http/https prefix")
    port: int = Field(default=443, description="S3 endpoint port")
    ssl: bool = Field(default=True, description="Whether to use SSL for S3 connections")
    access_key: str = Field(..., description="S3 access key")
    secret_key: str = Field(..., description="S3 secret key")
    buckets: S3BucketsConfig = Field(..., description="S3 bucket configuration")
    
    @property
    def endpoint_url(self) -> str:
        """Get the full endpoint URL with protocol."""
        protocol = "https" if self.ssl else "http"
        return f"{protocol}://{self.endpoint}"


class TemporalConfig(BaseModel):
    """Configuration for Temporal workflow engine."""
    server_address: str = Field(..., description="Address of the Temporal server")
    namespace: str = Field(default="default", description="Temporal namespace")
    enable_tls: bool = Field(default=False, description="Whether to use TLS for Temporal connection")
    task_queue: str = Field(..., description="Default task queue for workflows")
    workflow_id_prefix: str = Field(default="transcription-", description="Prefix for workflow IDs")
    max_concurrent_activities: int = Field(default=10, description="Maximum number of concurrent activities")


class ServerConfig(BaseModel):
    host: str = Field(default="0.0.0.0", description="Server host")
    port: int = Field(default=8000, description="Server port")
    workers: int = Field(default=1, description="Number of worker processes")
    job_polling_interval: float = Field(default=1.0, description="Job polling interval in seconds")
    job_batch_size: int = Field(default=5, description="Maximum number of jobs to process in one batch")
    max_retries: int = Field(default=3, description="Maximum number of job retry attempts")


class AppConfig(BaseModel):
    server: ServerConfig
    database: DatabaseConfig
    model: ModelConfig
    jwt: JWTConfig
    logging: LoggingConfig
    telemetry: OpenTelemetryConfig
    temporal: TemporalConfig
    s3: S3Config


def load_s3_config() -> S3Config:
    """
    Load S3 configuration from environment variables.
    """
    # Create S3BucketsConfig first
    buckets_config = S3BucketsConfig(
        work_area=get_env_str("S3__BUCKETS__WORK_AREA")
    )
    
    return S3Config(
        endpoint=get_env_str("S3__ENDPOINT"),
        port=get_env_int("S3__PORT", 443),
        ssl=get_env_bool("S3__SSL", True),
        access_key=get_env_str("S3__ACCESS_KEY"),
        secret_key=get_env_str("S3__SECRET_KEY"),
        buckets=buckets_config
    )


def load_server_config() -> ServerConfig:
    """
    Load server configuration from environment variables.
    """
    return ServerConfig(
        host=get_env_str("SERVER__HOST", "0.0.0.0"),
        port=get_env_int("SERVER__PORT", 8000),
        workers=get_env_int("SERVER__WORKERS", 1),
        job_polling_interval=get_env_float("SERVER__JOB_POLLING_INTERVAL", 1.0),
        job_batch_size=get_env_int("SERVER__JOB_BATCH_SIZE", 5),
        max_retries=get_env_int("SERVER__MAX_RETRIES", 3)
    )


def load_temporal_config() -> TemporalConfig:
    """
    Load Temporal configuration from environment variables.
    """
    return TemporalConfig(
        server_address=get_env_str("TEMPORAL__SERVER_ADDRESS"),
        namespace=get_env_str("TEMPORAL__NAMESPACE", "default"),
        enable_tls=get_env_bool("TEMPORAL__ENABLE_TLS", False),
        task_queue=get_env_str("TEMPORAL__TASK_QUEUE"),
        workflow_id_prefix=get_env_str("TEMPORAL__WORKFLOW_ID_PREFIX", "transcription-"),
        max_concurrent_activities=get_env_int("TEMPORAL__MAX_CONCURRENT_ACTIVITIES", 10)
    )


def load_database_config() -> DatabaseConfig:
    """
    Load database configuration from environment variables.
    """
    return DatabaseConfig(
        # cast to PostgresDsn to ensure it's a valid Postgres connection string
        dsn=PostgresDsn(get_env_str("DATABASE__DSN")),
        min_connections=get_env_int("DATABASE__MIN_CONNECTIONS", 5),
        max_connections=get_env_int("DATABASE__MAX_CONNECTIONS", 20),
        echo_queries=get_env_bool("DATABASE__ECHO_QUERIES", False)
    )


def load_model_config() -> ModelConfig:
    """
    Load model configuration from environment variables.
    """
    # Get acceleration value and validate it's a valid enum value
    accel_str = get_env_value("MODEL__ACCELERATION", "cpu")
    try:
        acceleration = HardwareAcceleration(accel_str)
    except ValueError:
        valid_values = ", ".join([e.value for e in HardwareAcceleration])
        raise ValueError(f"Invalid MODEL__ACCELERATION value: {accel_str}. Must be one of: {valid_values}")
    
    return ModelConfig(
        model_size=get_env_str("MODEL__MODEL_SIZE", "base"),
        acceleration=acceleration,
        cache_dir=get_env_str("MODEL__CACHE_DIR", "/tmp/whisperserve/models")
    )


def load_logging_config() -> LoggingConfig:
    """
    Load logging configuration from environment variables.
    """
    level_str = get_env_value("LOGGING__LEVEL", "INFO")
    try:
        level = LogLevel(level_str)
    except ValueError:
        valid_values = ", ".join([e.value for e in LogLevel])
        raise ValueError(f"Invalid LOGGING__LEVEL value: {level_str}. Must be one of: {valid_values}")
    
    return LoggingConfig(
        level=level,
        json_format=get_env_bool("LOGGING__JSON_FORMAT", True)
    )


def load_telemetry_config() -> OpenTelemetryConfig:
    """
    Load OpenTelemetry configuration from environment variables.
    """
    return OpenTelemetryConfig(
        enabled=get_env_bool("TELEMETRY__ENABLED", False),
        endpoint=get_env_value("TELEMETRY__ENDPOINT"),
        service_name=get_env_str("TELEMETRY__SERVICE_NAME", "whisperserve"),
        insecure=get_env_bool("TELEMETRY__INSECURE", False)
    )


def load_config() -> AppConfig:
    """
    Load application configuration from environment variables.
    """
    try:
        config = AppConfig(
            server=load_server_config(),
            database=load_database_config(),
            model=load_model_config(),
            jwt=load_jwt_config(),
            logging=load_logging_config(),
            telemetry=load_telemetry_config(),
            temporal=load_temporal_config(),
            s3=load_s3_config()
        )
        return config
    except ValueError as e:
        # Enhance error message with context
        raise ValueError(f"Configuration error: {str(e)}")
