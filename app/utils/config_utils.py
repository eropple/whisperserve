import os
from typing import Any, Optional


def get_env_value(key: str, default: Any = None, required: bool = False) -> Any:
    """
    Get environment variable value with proper error handling for required values.
    """
    value = os.environ.get(key)
    if value is None:
        if required:
            raise ValueError(f"Required environment variable {key} is not set")
        return default
    return value


def get_env_bool(key: str, default: bool = False) -> bool:
    """
    Get boolean value from environment variable.
    """
    value = get_env_value(key, None)
    if value is None:
        return default
    
    value = value.lower()
    if value in ("1", "true", "yes", "y", "on"):
        return True
    if value in ("0", "false", "no", "n", "off"):
        return False
    
    raise ValueError(f"Invalid boolean value for {key}: {value}")


def get_env_int(key: str, default: Optional[int] = None) -> Optional[int]:
    """
    Get integer value from environment variable.
    """
    value = get_env_value(key, None)
    if value is None:
        return default
    try:
        return int(value)
    except ValueError:
        raise ValueError(f"Invalid integer value for {key}: {value}")


def get_env_float(key: str, default: Optional[float] = None) -> Optional[float]:
    """
    Get float value from environment variable.
    """
    value = get_env_value(key, None)
    if value is None:
        return default
    try:
        return float(value)
    except ValueError:
        raise ValueError(f"Invalid float value for {key}: {value}")
