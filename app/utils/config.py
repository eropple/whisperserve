from enum import Enum
from typing import Dict, List, Optional, Any, Type, TypeVar, cast

from pydantic import BaseModel, Field, PostgresDsn, field_validator, model_validator

from app.utils.jwt_config import JWTConfig, load_jwt_config
from app.utils.config_utils import (
    get_env_value, get_env_bool, get_env_int, get_env_float
)

# Type definitions
T = TypeVar('T', bound=BaseModel)

class LogLevel(str, Enum):
    DEBUG = "DEBUG"
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"
    CRITICAL = "CRITICAL"


class BackendType(str, Enum):
    PYTORCH = "pytorch"
    FASTER_WHISPER = "faster_whisper"
    WHISPER_CPP = "whisper.cpp"
    MOCK = "mock"


class HardwareAcceleration(str, Enum):
    CPU = "cpu"
    CUDA = "cuda"
    ROCM = "rocm"
    METAL = "metal"


class ModelConfig(BaseModel):
    backend: BackendType = Field(default=BackendType.PYTORCH, description="Whisper implementation to use")
    model_size: str = Field(default="base", description="Model size (tiny, base, small, medium, large)")
    model_path: Optional[str] = Field(default=None, description="Custom path to model files")
    acceleration: HardwareAcceleration = Field(default=HardwareAcceleration.CPU, description="Hardware acceleration type")
    cache_dir: str = Field(default="/tmp/whisperserve/models", description="Directory to cache model files")


class DatabaseConfig(BaseModel):
    dsn: PostgresDsn = Field(..., description="PostgreSQL connection string")
    min_connections: int = Field(default=5, description="Minimum number of connections in the pool")
    max_connections: int = Field(default=20, description="Maximum number of connections in the pool")


class LoggingConfig(BaseModel):
    level: LogLevel = Field(default=LogLevel.INFO, description="Logging level")
    json_format: bool = Field(default=True, description="Use JSON format for logs")


class OpenTelemetryConfig(BaseModel):
    enabled: bool = Field(default=False, description="Enable OpenTelemetry integration")
    endpoint: Optional[str] = Field(default=None, description="OpenTelemetry collector endpoint")
    service_name: str = Field(default="whisperserve", description="Service name for OpenTelemetry")


class ServerConfig(BaseModel):
    host: str = Field(default="0.0.0.0", description="Server host")
    port: int = Field(default=8000, description="Server port")
    workers: int = Field(default=1, description="Number of worker processes")
    job_polling_interval: float = Field(default=1.0, description="Job polling interval in seconds")
    job_batch_size: int = Field(default=5, description="Maximum number of jobs to process in one batch")
    max_retries: int = Field(default=3, description="Maximum number of job retry attempts")


class AppConfig(BaseModel):
    server: ServerConfig = Field(default_factory=ServerConfig)
    database: DatabaseConfig
    model: ModelConfig = Field(default_factory=ModelConfig)
    jwt: JWTConfig
    logging: LoggingConfig = Field(default_factory=LoggingConfig)
    telemetry: OpenTelemetryConfig = Field(default_factory=OpenTelemetryConfig)


def load_server_config() -> ServerConfig:
    """
    Load server configuration from environment variables.
    """
    return ServerConfig(
        host=get_env_value("SERVER__HOST", "0.0.0.0"),
        port=get_env_int("SERVER__PORT", 8000),
        workers=get_env_int("SERVER__WORKERS", 1),
        job_polling_interval=get_env_float("SERVER__JOB_POLLING_INTERVAL", 1.0),
        job_batch_size=get_env_int("SERVER__JOB_BATCH_SIZE", 5),
        max_retries=get_env_int("SERVER__MAX_RETRIES", 3)
    )


def load_database_config() -> DatabaseConfig:
    """
    Load database configuration from environment variables.
    """
    return DatabaseConfig(
        dsn=get_env_value("DATABASE__DSN", required=True),
        min_connections=get_env_int("DATABASE__MIN_CONNECTIONS", 5),
        max_connections=get_env_int("DATABASE__MAX_CONNECTIONS", 20)
    )


def load_model_config() -> ModelConfig:
    """
    Load model configuration from environment variables.
    """
    # Get backend value and validate it's a valid enum value
    backend_str = get_env_value("MODEL__BACKEND", "pytorch")
    try:
        backend = BackendType(backend_str)
    except ValueError:
        valid_values = ", ".join([e.value for e in BackendType])
        raise ValueError(f"Invalid MODEL__BACKEND value: {backend_str}. Must be one of: {valid_values}")
    
    # Get acceleration value and validate it's a valid enum value
    accel_str = get_env_value("MODEL__ACCELERATION", "cpu")
    try:
        acceleration = HardwareAcceleration(accel_str)
    except ValueError:
        valid_values = ", ".join([e.value for e in HardwareAcceleration])
        raise ValueError(f"Invalid MODEL__ACCELERATION value: {accel_str}. Must be one of: {valid_values}")
    
    return ModelConfig(
        backend=backend,
        model_size=get_env_value("MODEL__MODEL_SIZE", "base"),
        model_path=get_env_value("MODEL__MODEL_PATH"),
        acceleration=acceleration,
        cache_dir=get_env_value("MODEL__CACHE_DIR", "/tmp/whisperserve/models")
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
        service_name=get_env_value("TELEMETRY__SERVICE_NAME", "whisperserve")
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
            telemetry=load_telemetry_config()
        )
        return config
    except ValueError as e:
        # Enhance error message with context
        raise ValueError(f"Configuration error: {str(e)}")
