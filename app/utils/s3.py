"""S3 client utilities."""
import boto3
from botocore.client import Config, BaseClient

from app.utils.config import S3Config

def create_s3_client(config: S3Config) -> BaseClient:
    """Create and configure an S3 client."""
    return boto3.client(
        's3',
        endpoint_url=config.endpoint_url,
        aws_access_key_id=config.access_key,
        aws_secret_access_key=config.secret_key,
        config=Config(signature_version='s3v4'),
        use_ssl=config.ssl,
    )
