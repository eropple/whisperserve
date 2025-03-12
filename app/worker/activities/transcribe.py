"""Transcription activity for Temporal."""
import os
import time
from typing import Any
from urllib.parse import urlparse

from temporalio import activity

from app.logging import get_logger
from app.utils.config import load_config
from app.worker.models import TranscribeMediaInput, TranscribeMediaOutput

@activity.defn
async def transcribe_media(input_data: TranscribeMediaInput) -> TranscribeMediaOutput:
    """
    Transcribe audio/video file using the configured model backend.
    
    Args:
        input_data: Activity input parameters
        
    Returns:
        Transcription results
    """
    # Load config inside the activity
    config = load_config()
    
    # Import boto3 inside activity
    import boto3
    s3_client = boto3.client('s3')
    
    logger = get_logger().bind(
        activity="transcribe_media", 
        job_id=input_data.job_id,
        tenant_id=input_data.tenant_id
    )
    
    logger.info("transcription_started", 
                s3_location=input_data.s3_location,
                options=input_data.options)
    
    # Create a temporary directory for this job
    temp_dir = os.path.join("/tmp/whisperserve", input_data.job_id)
    os.makedirs(temp_dir, exist_ok=True)
    
    try:
        # Get file from S3
        bucket = input_data.s3_location.bucket
        key = input_data.s3_location.key
        
        # Extract filename from S3 key
        filename = os.path.basename(key)
        local_path = os.path.join(temp_dir, filename)
        
        # Download from S3
        logger.info("downloading_from_s3", bucket=bucket, key=key)
        s3_client.download_file(bucket, key, local_path)
        
        # Now process the file
        start_time = time.time()
        
        # Convert processing options
        options = input_data.options.copy()
        options["processing_mode"] = input_data.processing_mode
        if input_data.track_index is not None:
            options["track_index"] = input_data.track_index

        raise NotImplementedError("TBD")
        
        # # Here you would create and use the appropriate backend based on config
        # # For now, we'll use a mock backend
        # backend = MockBackend(model_size="base")
        # await backend.initialize()
        
        # # Process with the model backend
        # result = await backend.transcribe(audio_path=local_path, options=options)
        
        # processing_time = time.time() - start_time
        # logger.info("transcription_completed", 
        #             duration=result.duration,
        #             processing_time=processing_time,
        #             language=result.language)
        
        # # Return the result
        # return TranscribeMediaOutput(
        #     text=result.text,
        #     segments=result.segments,
        #     language=result.language,
        #     duration=result.duration,
        #     processing_time=processing_time
        # )
    
    except Exception as e:
        logger.exception("transcription_failed", error=str(e))
        raise
    finally:
        # Clean up temp files
        try:
            import shutil
            shutil.rmtree(temp_dir, ignore_errors=True)
        except Exception as e:
            logger.warning("cleanup_failed", error=str(e))
