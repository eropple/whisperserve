import pytest
import time
from pathlib import Path
from typing import Dict, Any

from app.worker.backends.base import TranscriptionResult
from app.worker.backends.mock import MockBackend

# Test data
TEST_MOCK_RESULTS = {
    "default": {
        "text": "This is a test transcription.",
        "segments": [
            {
                "id": 0,
                "start": 0.0,
                "end": 2.0,
                "text": "This is a test"
            },
            {
                "id": 1,
                "start": 2.0,
                "end": 4.0,
                "text": "transcription."
            }
        ],
        "language": "en",
        "duration": 4.0
    },
    "custom_key": {
        "text": "This is a custom test result.",
        "segments": [
            {
                "id": 0,
                "start": 0.0,
                "end": 5.0,
                "text": "This is a custom test result."
            }
        ],
        "language": "fr",  # Different language to test selection
        "duration": 5.0
    }
}

@pytest.fixture
def mock_backend():
    """Create a mock backend with test results."""
    return MockBackend(
        model_size="test_model",
        latency=0.1,  # Fast latency for tests
        mock_results=TEST_MOCK_RESULTS
    )

@pytest.mark.asyncio
async def test_initialize(mock_backend):
    """Test that the mock backend initializes successfully."""
    result = await mock_backend.initialize()
    assert result is True

@pytest.mark.asyncio
async def test_transcribe_default(mock_backend):
    """Test transcription with default result."""
    # Use a path that doesn't contain any custom keys
    result = await mock_backend.transcribe("/path/to/some/audio.mp3")
    
    # Verify the result is a TranscriptionResult
    assert isinstance(result, TranscriptionResult)
    
    # Check content matches our test data
    assert result.text == TEST_MOCK_RESULTS["default"]["text"]
    assert result.language == TEST_MOCK_RESULTS["default"]["language"]
    assert result.duration == TEST_MOCK_RESULTS["default"]["duration"]
    assert len(result.segments) == len(TEST_MOCK_RESULTS["default"]["segments"])

@pytest.mark.asyncio
async def test_transcribe_custom_key(mock_backend):
    """Test transcription with custom key selection."""
    # Use a path that contains our custom key
    result = await mock_backend.transcribe("/path/with/custom_key/audio.mp3")
    
    # Verify we got the custom result
    assert result.text == TEST_MOCK_RESULTS["custom_key"]["text"]
    assert result.language == TEST_MOCK_RESULTS["custom_key"]["language"]
    assert result.duration == TEST_MOCK_RESULTS["custom_key"]["duration"]

@pytest.mark.asyncio
async def test_transcribe_processing_time(mock_backend):
    """Test that processing time simulation works."""
    start_time = time.time()
    result = await mock_backend.transcribe("/test/audio.mp3")
    elapsed_time = time.time() - start_time
    
    # Since we set latency to 0.1 and default duration is 4.0,
    # processing time should be around 0.4s (but capped at 2s)
    # Allow some wiggle room for test execution
    expected_time = min(TEST_MOCK_RESULTS["default"]["duration"] * 0.1, 2.0)
    assert elapsed_time > 0
    assert abs(elapsed_time - expected_time) < 0.2  # Allow 200ms variance

def test_backend_properties(mock_backend):
    """Test the backend property getters."""
    assert mock_backend.name == "mock"
    assert mock_backend.model_size == "test_model"
    assert mock_backend.supports_word_timestamps is True

@pytest.mark.asyncio
async def test_shutdown(mock_backend):
    """Test that shutdown completes without errors."""
    await mock_backend.shutdown()
    # No assertions needed - we're just checking it doesn't raise exceptions
