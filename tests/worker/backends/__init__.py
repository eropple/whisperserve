from typing import Dict, Type

from app.utils.config import ModelConfig, HardwareAcceleration
from app.worker.backends.base import ModelBackend
from app.worker.backends.mock import MockBackend
from app.worker.backends.whisperx_cpu_backend import WhisperXCPUBackend

# Import other backends as they're implemented

def create_backend(config: ModelConfig) -> ModelBackend:
    """
    Create a model backend based on configuration.
    
    Args:
        config: Model configuration
        
    Returns:
        Appropriate model backend instance
        
    Raises:
        ValueError: If the backend type or hardware acceleration is not supported
    """
    if config.acceleration == HardwareAcceleration.MOCK:
        return MockBackend(model_size=config.model_size)
    
    # For WhisperX, we'll use the PyTorch backend type for now
    if config.acceleration == HardwareAcceleration.CPU:
        # Use WhisperX backend for both CPU and CUDA
        return WhisperXCPUBackend(config)
    
    # Handle other backends as they're implemented
    # if config.backend == BackendType.FASTER_WHISPER:
    #     if config.acceleration == HardwareAcceleration.CPU:
    #         return FasterWhisperCPUBackend(config)
    #     elif config.acceleration == HardwareAcceleration.CUDA:
    #         return FasterWhisperGPUBackend(config)
    
    # If we reach here, the combination is not supported
    raise ValueError(
        f"Unsupported acceleration type: {config.acceleration.value}"
    )
