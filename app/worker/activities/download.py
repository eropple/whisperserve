"""Media download activity for Temporal."""
import os
import hashlib
from pathlib import Path
from urllib.parse import urlparse

import aiohttp
import aiofiles
import mimetypes
from temporalio import activity

from app.logging import get_logger
from app.utils.config import load_config
from app.worker.models import DownloadMediaInput, DownloadMediaOutput, S3Location

@activity.defn
async def download_media(input_data: DownloadMediaInput) -> DownloadMediaOutput:
    """
    Download media file from URL and upload to S3 work area.
    
    Args:
        input_data: Activity input parameters
        
    Returns:
        Download result with S3 location
    """
    config = load_config()
    
    logger = get_logger().bind(
        activity="download_media", 
        job_id=input_data.job_id,
        tenant_id=input_data.tenant_id
    )
    
    workflow_id = activity.info().workflow_id
    logger.info("media_download_started", 
                url=input_data.media_url, 
                workflow_id=workflow_id)
    
    temp_dir = Path(f"/tmp/whisperserve/{input_data.job_id}")
    os.makedirs(temp_dir, exist_ok=True)
    
    try:
        # Extract filename from URL or use job ID
        url_path = urlparse(input_data.media_url).path
        filename = os.path.basename(url_path) or f"media_{input_data.job_id}"
        temp_file = temp_dir / filename
        
        # Determine file extension for the S3 key
        _, file_extension = os.path.splitext(filename)
        if not file_extension:
            # Try to guess extension from the URL's content type
            content_type, _ = mimetypes.guess_type(input_data.media_url)
            if content_type:
                extension = mimetypes.guess_extension(content_type)
                if extension:
                    file_extension = extension
        
        # If still no extension, use a default
        if not file_extension:
            file_extension = ".bin"
        
        # Download the file locally first
        content_type = None
        async with aiohttp.ClientSession() as session:
            async with session.get(input_data.media_url) as response:
                if response.status != 200:
                    error_msg = f"Failed to download media: HTTP {response.status}"
                    logger.error("media_download_failed", 
                                status=response.status,
                                error=error_msg)
                    raise ValueError(error_msg)
                
                # Get content type from the response
                content_type = response.headers.get('Content-Type')
                
                # Stream to file while calculating hash
                hash_sha256 = hashlib.sha256()
                total_bytes = 0
                
                async with aiofiles.open(temp_file, 'wb') as f:
                    async for chunk in response.content.iter_chunked(1024 * 1024):
                        await f.write(chunk)
                        hash_sha256.update(chunk)
                        total_bytes += len(chunk)
                
                # Verify hash if provided
                calculated_hash = hash_sha256.hexdigest()
                if input_data.expected_hash and calculated_hash != input_data.expected_hash:
                    error_msg = "Media file hash mismatch"
                    logger.error("hash_verification_failed", 
                                expected=input_data.expected_hash,
                                calculated=calculated_hash)
                    raise ValueError(error_msg)
        
        # Define S3 key using workflow ID as prefix, retaining file extension
        s3_key = f"{workflow_id}/original{file_extension}"
        
        # Upload to S3 work area with content type metadata
        work_bucket = config.s3.buckets.work_area
        
        # Prepare extra arguments including content type
        extra_args = {}
        if content_type:
            extra_args['Content-Type'] = content_type
        
        # Add metadata to track the source
        extra_args['Metadata'] = {
            'tenant_id': input_data.tenant_id,
            'job_id': input_data.job_id,
            'source_url': input_data.media_url,
            'sha256': calculated_hash
        }
        
        from app.utils.s3 import create_s3_client
        s3_client = create_s3_client(config.s3, telemetry_config=config.telemetry)
        
        # Upload to S3
        s3_client.upload_file(
            str(temp_file),
            work_bucket,
            s3_key,
            ExtraArgs=extra_args
        )
        
        logger.info("media_uploaded_to_s3", 
                    bucket=work_bucket,
                    key=s3_key,
                    content_type=content_type,
                    file_size=total_bytes,
                    sha256=calculated_hash)
        
        # Clean up local file after successful upload
        os.unlink(temp_file)
        
        return DownloadMediaOutput(
            s3_location=S3Location(
                bucket=work_bucket,
                key=s3_key
            ),
            file_size=total_bytes,
            sha256=calculated_hash
        )
    
    except Exception as e:
        logger.exception("media_download_failed", error=str(e))
        # Clean up temp directory in case of failure
        try:
            if os.path.exists(temp_file):
                os.unlink(temp_file)
        except:
            pass
        raise
    finally:
        # Clean up temp directory
        try:
            os.rmdir(temp_dir)
        except:
            pass
