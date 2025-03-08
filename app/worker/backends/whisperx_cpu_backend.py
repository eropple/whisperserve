import gc
import os
import time
from typing import Dict, Any, Optional, List
from pathlib import Path

import whisperx
import torch
import numpy as np
import structlog

from app.worker.backends.base import ModelBackend, TranscriptionResult
from app.utils.config import ModelConfig, HardwareAcceleration

# Set up structured logger
logger = structlog.get_logger()

class WhisperXCPUBackend(ModelBackend):
    """
    Backend that uses WhisperX for transcription with optional alignment.
    This implementation is optimized for CPU usage.
    """
    
    def __init__(self, config: ModelConfig):
        """
        Initialize WhisperX backend.
        
        Args:
            config: Model configuration
        """
        self.config = config
        self.model = None
        self.align_model = None
        self.align_metadata = None
        self.log = logger.bind(backend="whisperx", model_size=config.model_size)
        
        # Use the model path if provided, otherwise use cache_dir
        self.download_root = config.model_path or config.cache_dir
        
        # Default to CPU device
        self.device = "cpu"
        
        # Set compute type based on hardware
        # For CPU, use int8 for better performance
        self.compute_type = "int8"
        
        # Set batch size - smaller for CPU to avoid memory issues
        self.batch_size = 8
        
        # Flag to enable/disable alignment
        # For CPU, we'll make alignment optional since it's computationally expensive
        self.enable_alignment = True
        
        # We don't enable diarization by default on CPU as it's very resource intensive
        self.enable_diarization = False
    
    async def initialize(self) -> bool:
        """
        Initialize the WhisperX models.
        For CPU usage, we'll load models with appropriate optimizations.
        
        Returns:
            True if initialization was successful, False otherwise
        """
        try:
            self.log.info("initializing_whisperx", device=self.device, compute_type=self.compute_type)
            
            # Create cache directory if it doesn't exist
            os.makedirs(self.download_root, exist_ok=True)
            
            # Load the main transcription model
            # For CPU, we use a lower precision model for better performance
            self.model = whisperx.load_model(
                self.config.model_size,
                self.device,
                compute_type=self.compute_type,
                download_root=self.download_root,
                language="en"  # Default to English, will be detected during transcription
            )
            
            self.log.info("whisperx_model_loaded", model_size=self.config.model_size)
            return True
            
        except Exception as e:
            self.log.exception("whisperx_initialization_failed", error=str(e))
            return False
    
    async def transcribe(
        self, audio_path: str, options: Dict[str, Any] = {}
    ) -> TranscriptionResult:
        """
        Transcribe audio using WhisperX.
        
        Args:
            audio_path: Path to audio file
            options: Transcription options
                - processing_mode: How to process audio (downmix, select, multitrack)
                - track_index: Which track to process (for select mode)
                - enable_alignment: Whether to run the alignment model (default: True)
                - language: Override language detection (default: auto-detect)
        
        Returns:
            TranscriptionResult object with transcription data
        """
        if self.model is None:
            raise RuntimeError("WhisperX model not initialized. Call initialize() first.")
        
        options = options or {}
        processing_mode = options.get("processing_mode", "downmix")
        track_index = options.get("track_index")
        language_override = options.get("language")
        
        # Check if alignment should be enabled for this request
        enable_alignment = options.get("enable_alignment", self.enable_alignment)
        
        # Start timing
        start_time = time.time()
        
        try:
            self.log.info("loading_audio", path=audio_path)
            
            # Load audio file
            audio = whisperx.load_audio(audio_path)
            
            # If we're using 'select' mode and track_index is specified,
            # we would handle audio track selection here. 
            # Note: simple implementation for now, could be expanded
            if processing_mode == "select" and track_index is not None:
                self.log.info("mode_select_not_implemented", 
                             message="Track selection not implemented in WhisperX backend yet")
            
            self.log.info("starting_transcription")
            
            # Transcribe with WhisperX
            # Set batch size lower for CPU to avoid memory issues
            result = self.model.transcribe(
                audio, 
                batch_size=self.batch_size,
                language=language_override
            )
            
            detected_language = result.get("language", "unknown")
            self.log.info("transcription_completed", language=detected_language)
            
            # Run alignment if enabled
            if enable_alignment and len(result["segments"]) > 0:
                self.log.info("starting_alignment", language=detected_language)
                
                # Load alignment model for detected language if not already loaded
                # We load this on-demand to save memory
                if (self.align_model is None or 
                    self.align_metadata is None or 
                    self.align_metadata.get("language_code") != detected_language):
                    
                    self.log.info("loading_alignment_model", language=detected_language)
                    self.align_model, self.align_metadata = whisperx.load_align_model(
                        language_code=detected_language,
                        device=self.device
                    )
                
                # Run alignment
                result = whisperx.align(
                    result["segments"],
                    self.align_model,
                    self.align_metadata,
                    audio,
                    self.device,
                    return_char_alignments=False
                )
                
                self.log.info("alignment_completed")
            
            # Convert WhisperX result to TranscriptionResult format
            segments = result["segments"]
            full_text = " ".join([seg.get("text", "").strip() for seg in segments])
            
            # Map WhisperX segments to our format
            mapped_segments = []
            for i, seg in enumerate(segments):
                mapped_segments.append({
                    "id": i,
                    "start": seg.get("start", 0.0),
                    "end": seg.get("end", 0.0),
                    "text": seg.get("text", "").strip(),
                    "words": seg.get("words", [])
                })
            
            # Calculate duration from segments
            duration = max([seg.get("end", 0.0) for seg in segments]) if segments else 0.0
            
            # Calculate processing time
            processing_time = time.time() - start_time
            
            self.log.info("transcription_result_prepared", 
                         segment_count=len(mapped_segments),
                         duration=duration,
                         processing_time=processing_time)
            
            return TranscriptionResult(
                text=full_text,
                segments=mapped_segments,
                language=detected_language,
                duration=duration,
                processing_time=processing_time
            )
            
        except Exception as e:
            self.log.exception("transcription_failed", error=str(e))
            raise
    
    async def shutdown(self) -> None:
        """Clean up resources."""
        try:
            self.log.info("shutting_down_whisperx")
            
            # Delete models to free memory
            if self.align_model is not None:
                del self.align_model
                self.align_model = None
            
            if self.model is not None:
                del self.model
                self.model = None
            
            # Force garbage collection
            gc.collect()
            if torch.cuda.is_available():
                torch.cuda.empty_cache()
                
            self.log.info("whisperx_shutdown_completed")
        except Exception as e:
            self.log.error("whisperx_shutdown_error", error=str(e))
    
    @property
    def name(self) -> str:
        return "whisperx"
    
    @property
    def model_size(self) -> str:
        return self.config.model_size
    
    @property
    def supports_word_timestamps(self) -> bool:
        return True
