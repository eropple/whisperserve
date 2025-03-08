import os
from typing import Any, Optional


def get_env_value(key: str, default: Any = None) -> Any | None:
    """
    Get environment variable value with proper error handling for required values.
    """
    value = os.environ.get(key)
    if value is None:
        return default
    return value

def get_env_str(key: str, default: Optional[str] = None) -> str:
    """
    Get string value from environment variable.
    """
    value = get_env_value(key, None)
    if value is None:
        if default is not None:
            return default
        else:
            raise ValueError(f"Required environment variable {key} is not set")
    return value

def get_env_bool(key: str, default: Optional[bool] = None) -> bool:
    """
    Get boolean value from environment variable.
    """
    value = get_env_value(key, None)
    if value is None:
        if default is not None:
            return default
        else:
            raise ValueError(f"Required environment variable {key} is not set")
    
    value = value.lower()
    if value in ("1", "true", "yes", "y", "on"):
        return True
    if value in ("0", "false", "no", "n", "off"):
        return False
    
    raise ValueError(f"Invalid boolean value for {key}: {value}")


def get_env_int(key: str, default: Optional[int] = None) -> int:
    """
    Get integer value from environment variable.
    """
    value = get_env_value(key, None)
    if value is None:
        if default is not None:
            return default
        else:
            raise ValueError(f"Required environment variable {key} is not set")
    try:
        return int(value)
    except ValueError:
        raise ValueError(f"Invalid integer value for {key}: {value}")


def get_env_float(key: str, default: Optional[float] = None) -> float:
    """
    Get float value from environment variable.
    """
    value = get_env_value(key, None)
    if value is None:
        if default is not None:
            return default
        else:
            raise ValueError(f"Required environment variable {key} is not set")
    try:
        return float(value)
    except ValueError:
        raise ValueError(f"Invalid float value for {key}: {value}")
