import time
from typing import Dict, Any, Optional, List

from app.worker.backends.base import ModelBackend, TranscriptionResult

class MockBackend(ModelBackend):
    """Mock backend that returns predetermined results for testing."""
    
    def __init__(
        self, 
        model_size: str = "mock", 
        latency: float = 1.0,
        mock_results: Dict[str, Any] | None = None
    ):
        """
        Initialize mock backend.
        
        Args:
            model_size: Simulated model size
            latency: Simulated processing time in seconds per second of audio
            mock_results: Dictionary of mock transcription results to use
        """
        self._model_size = model_size
        self.latency = latency
        
        # Default mock results if none provided
        self._mock_results = mock_results or {
            "default": {
                "text": "This is a mock transcription for testing purposes.",
                "segments": [
                    {
                        "id": 0,
                        "start": 0.0,
                        "end": 5.0,
                        "text": "This is a mock transcription"
                    },
                    {
                        "id": 1,
                        "start": 5.0,
                        "end": 10.0,
                        "text": "for testing purposes."
                    }
                ],
                "language": "en",
                "duration": 10.0
            }
        }
    
    async def initialize(self) -> bool:
        """Mock initialization always succeeds."""
        return True
    
    async def transcribe(
        self, audio_path: str, options: Dict[str, Any] = {}
    ) -> TranscriptionResult:
        """
        Return a mock transcription result.
        
        If audio_path contains a key from the mock results dictionary,
        that result will be used. Otherwise, the default result is used.
        """
        options = options or {}
        
        # Determine which mock result to use based on filename
        result_key = "default"
        for key in self._mock_results.keys():
            if key in audio_path:
                result_key = key
                break
        
        mock_data = self._mock_results[result_key]
        
        # Simulate processing time based on audio duration
        duration = mock_data.get("duration", 10.0)
        processing_time = self.latency * duration
        # Use asyncio.sleep in the real implementation
        time.sleep(min(processing_time, 2.0))  # Cap at 2 seconds for tests
        
        return TranscriptionResult(
            text=mock_data["text"],
            segments=mock_data["segments"],
            language=mock_data.get("language", "en"),
            duration=duration,
            processing_time=processing_time
        )
    
    async def shutdown(self) -> None:
        """Nothing to clean up."""
        pass
    
    @property
    def name(self) -> str:
        return "mock"
    
    @property
    def model_size(self) -> str:
        return self._model_size
    
    @property
    def supports_word_timestamps(self) -> bool:
        return True
