# utils/s3.py
import boto3
from botocore.config import Config as BotoConfig
from boto3.s3.transfer import TransferConfig
from django.conf import settings

def resilient_upload_fileobj(bucket: str, key: str, file_obj, content_type: str | None = None):
    """
    Fallback uploader using a fresh client + tuned TransferConfig.
    """
    extra_args = {"ACL": "public-read"}
    if content_type:
        extra_args["ContentType"] = content_type

    client = boto3.client(
        "s3",
        aws_access_key_id=getattr(settings, "AWS_ACCESS_KEY_ID", None),
        aws_secret_access_key=getattr(settings, "AWS_SECRET_ACCESS_KEY", None),
        region_name=getattr(settings, "AWS_S3_REGION_NAME", None),
        endpoint_url=getattr(settings, "AWS_S3_ENDPOINT_URL", None),
        config=BotoConfig(
            retries={"max_attempts": 6, "mode": "standard"},
            connect_timeout=30,
            read_timeout=180,
            max_pool_connections=20,
            tcp_keepalive=True,
            signature_version="s3v4",
            s3={"addressing_style": "path"},
        ),
    )

    # minimum chunk is 5MB
    tcfg = TransferConfig(multipart_threshold=5 * 1024 * 1024,
                          multipart_chunksize=5 * 1024 * 1024,
                          max_concurrency=2,  # keep low in small containers
                          use_threads=False)

    # rewind just in case
    try:
        file_obj.seek(0)
    except Exception:
        pass

    client.upload_fileobj(file_obj, bucket, key, ExtraArgs=extra_args, Config=tcfg)
