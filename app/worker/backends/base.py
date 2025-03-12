from abc import ABC, abstractmethod
from typing import Dict, Any, Optional

class TranscriptionResult:
    """Structured result from a transcription operation."""
    
    def __init__(
        self,
        text: str,
        segments: list[Dict[str, Any]],
        language: str,
        duration: float,
        processing_time: float,
    ):
        self.text = text  # Full transcription text
        self.segments = segments  # Time-aligned segments
        self.language = language  # Detected language
        self.duration = duration  # Media duration in seconds
        self.processing_time = processing_time  # Processing time in seconds
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert result to dictionary for API responses and storage."""
        return {
            "text": self.text,
            "segments": self.segments,
            "language": self.language,
            "duration": self.duration,
            "processing_time": self.processing_time,
        }

class ModelBackend(ABC):
    """Abstract base class for Whisper model backends."""
    
    @abstractmethod
    async def initialize(self) -> bool:
        """Initialize the model and return True if successful."""
        pass
    
    @abstractmethod
    async def transcribe(
        self, audio_path: str, options: Dict[str, Any] = {}
    ) -> TranscriptionResult:
        """
        Transcribe audio file and return structured result.
        
        Args:
            audio_path: Path to the audio file
            options: Optional transcription parameters
            
        Returns:
            TranscriptionResult: Structured transcription result
        """
        pass
    
    @abstractmethod
    async def shutdown(self) -> None:
        """Clean up resources."""
        pass
    
    @property
    @abstractmethod
    def name(self) -> str:
        """Get the backend name."""
        pass
    
    @property
    @abstractmethod
    def model_size(self) -> str:
        """Get the model size."""
        pass
    
    @property
    @abstractmethod
    def supports_word_timestamps(self) -> bool:
        """Check if the backend supports word-level timestamps."""
        pass
