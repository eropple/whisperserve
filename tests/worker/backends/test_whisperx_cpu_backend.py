import json
import os
import pytest
from pathlib import Path

from app.utils.config import ModelConfig, HardwareAcceleration
from app.worker.backends.whisperx_cpu_backend import WhisperXCPUBackend

# Constants for test configuration
TEST_DATA_DIR = Path('/home/ed/Development/eropple/whisperserve/test-data')
SHORT_AUDIO_FILE = TEST_DATA_DIR / 'eisenhower-farewell_address-short-64kbps.mp3'
SHORT_BASE_EXPECTED = TEST_DATA_DIR / 'eisenhower-farewell_address-short-64kbps-cpu.base.json'

# Tolerance parameters for comparison
TIME_TOLERANCE = 0.3  # Seconds of tolerance for start/end times
CONFIDENCE_TOLERANCE = 0.15  # Tolerance for confidence scores
TEXT_MATCH_REQUIRED = 0.85  # Minimum ratio of segments where text must match

@pytest.fixture
def model_config():
    """Create a model configuration for testing."""
    return ModelConfig(
        model_size="base",
        acceleration=HardwareAcceleration.CPU,
        cache_dir="/tmp/whisperserve-test/models"
    )

@pytest.fixture
def expected_results():
    """Load expected transcription results from reference file."""
    with open(SHORT_BASE_EXPECTED, 'r') as f:
        return json.load(f)

def load_segments_for_comparison(result_dict):
    """Extract segments from result dict into a format suitable for comparison."""
    if 'segments' in result_dict:
        return result_dict['segments']
    return []

def are_segments_similar(actual_segment, expected_segment, time_tolerance, text_match=True):
    """
    Compare segments with tolerance for timing differences.
    
    Args:
        actual_segment: Segment from actual transcription
        expected_segment: Segment from expected results
        time_tolerance: Tolerance in seconds for start/end times
        text_match: Whether to require text matching (set to False for initial alignment check)
    
    Returns:
        Boolean indicating if segments are similar enough
    """
    # Check start time is within tolerance
    if abs(float(actual_segment.get('start', 0)) - float(expected_segment.get('start', 0))) > time_tolerance:
        return False
    
    # Check end time is within tolerance
    if abs(float(actual_segment.get('end', 0)) - float(expected_segment.get('end', 0))) > time_tolerance:
        return False
    
    # If text matching is required, check text similarity
    if text_match and actual_segment.get('text', '').strip() != expected_segment.get('text', '').strip():
        return False
    
    return True

def compare_confidence_scores(actual_words, expected_words, tolerance):
    """
    Compare word confidence scores with tolerance.
    
    Returns:
        Tuple of (match_count, total_count) for words with similar confidence
    """
    if not actual_words or not expected_words:
        print(f"No words to compare: actual={len(actual_words) if actual_words else 0}, expected={len(expected_words) if expected_words else 0}")
        return 0, 0
    
    # Match words by their timing and text
    matches = 0
    total = min(len(actual_words), len(expected_words))
    
    print(f"\nComparing confidence scores for {total} words:")
    print(f"Actual words structure: {actual_words[0] if actual_words else 'empty'}")
    print(f"Expected words structure: {expected_words[0] if expected_words else 'empty'}")
    
    for i, (a_word, e_word) in enumerate(zip(actual_words, expected_words)):
        # The key is 'score', not 'confidence'
        a_conf = a_word.get('score', None)
        e_conf = e_word.get('score', None)
        
        # Convert numpy float64 to standard float if needed
        if a_conf is not None and hasattr(a_conf, 'item'):
            a_conf = a_conf.item()  # Convert np.float64 to Python float
        
        if a_conf is None or e_conf is None:
            print(f"Word {i}: Missing score - actual: {a_conf}, expected: {e_conf}")
            continue
            
        # Check if confidence is within tolerance
        diff = abs(float(a_conf) - float(e_conf))
        is_match = diff <= tolerance
        
        if i < 10 or is_match:  # Print first 10 words and any matches
            print(f"Word {i}: '{a_word.get('word', '')}' vs '{e_word.get('word', '')}' - "
                  f"score: {a_conf:.3f} vs {e_conf:.3f}, diff: {diff:.3f}, match: {is_match}")
        
        if is_match:
            matches += 1
    
    return matches, total

@pytest.mark.asyncio
async def test_whisperx_cpu_transcription(model_config, expected_results):
    """Test WhisperX CPU backend transcription against reference data."""
    # Skip test if audio file doesn't exist
    if not os.path.exists(SHORT_AUDIO_FILE):
        pytest.skip(f"Test audio file not found: {SHORT_AUDIO_FILE}")
    
    # Create backend
    backend = WhisperXCPUBackend(model_config)
    
    try:
        # Initialize backend
        initialized = await backend.initialize()
        assert initialized, "Backend failed to initialize"
        
        # Run transcription
        result = await backend.transcribe(str(SHORT_AUDIO_FILE))
        
        # Convert result to dictionary for comparison
        result_dict = result.to_dict()
        
        # Compare basic metadata
        assert result_dict["language"] == expected_results["language"], "Language mismatch"
        
        # Duration should be within 10% of expected
        assert abs(result_dict["duration"] - expected_results["duration"]) <= expected_results["duration"] * 0.1, "Duration significantly different"
        
        # Get segments for comparison
        actual_segments = load_segments_for_comparison(result_dict)
        expected_segments = load_segments_for_comparison(expected_results)
        
        # Verify we have a reasonable number of segments
        assert len(actual_segments) >= 0.9 * len(expected_segments), f"Too few segments: got {len(actual_segments)}, expected ~{len(expected_segments)}"
        assert len(actual_segments) <= 1.1 * len(expected_segments), f"Too many segments: got {len(actual_segments)}, expected ~{len(expected_segments)}"
        
        # Compare segments
        text_matches = 0
        timing_matches = 0
        confidence_matches = 0
        confidence_total = 0
        
        # First pass: check how many segments have similar timing, regardless of text
        segment_alignment = []
        for exp_seg in expected_segments:
            for i, act_seg in enumerate(actual_segments):
                if are_segments_similar(act_seg, exp_seg, TIME_TOLERANCE, text_match=False):
                    segment_alignment.append((i, exp_seg))
                    timing_matches += 1
                    break
        
        # Check timing alignment is sufficient
        assert timing_matches >= len(expected_segments) * 0.8, f"Insufficient timing matches: {timing_matches}/{len(expected_segments)}"
        
        # Second pass: check text and word confidence using aligned segments
        for i, exp_seg in segment_alignment:
            act_seg = actual_segments[i]
            
            # Check if text matches
            if act_seg.get('text', '').strip() == exp_seg.get('text', '').strip():
                text_matches += 1
            
            # Debug segment structure
            print(f"\nSegment comparison:")
            print(f"Actual: {act_seg}")
            print(f"Expected: {exp_seg}")
            
            # Check if 'words' key exists
            if 'words' not in act_seg:
                print(f"Warning: 'words' key missing in actual segment")
            if 'words' not in exp_seg:
                print(f"Warning: 'words' key missing in expected segment")
            
            # Check word confidence scores
            act_words = act_seg.get('words', [])
            exp_words = exp_seg.get('words', [])
            
            print(f"Word count: actual={len(act_words)}, expected={len(exp_words)}")
            
            matches, total = compare_confidence_scores(
                act_words, 
                exp_words,
                CONFIDENCE_TOLERANCE
            )
            confidence_matches += matches
            confidence_total += total
        
        # Calculate match ratios
        text_match_ratio = text_matches / len(segment_alignment) if segment_alignment else 0
        confidence_match_ratio = confidence_matches / confidence_total if confidence_total else 1.0
        
        # Log match statistics
        print(f"Timing matches: {timing_matches}/{len(expected_segments)} ({timing_matches/len(expected_segments):.2f})")
        print(f"Text matches: {text_matches}/{len(segment_alignment)} ({text_match_ratio:.2f})")
        print(f"Confidence matches: {confidence_matches}/{confidence_total} ({confidence_match_ratio:.2f})")
        
        # Final assertions
        assert text_match_ratio >= TEXT_MATCH_REQUIRED, f"Text match ratio too low: {text_match_ratio:.2f}"
        
        # Skip confidence assertion if we have no confidence values to compare
        if confidence_total > 0:
            assert confidence_match_ratio >= 0.7, f"Confidence score match ratio too low: {confidence_match_ratio:.2f}"
        else:
            print("WARNING: No confidence scores to compare - skipping confidence assertion")
        
    finally:
        # Clean up
        await backend.shutdown()
