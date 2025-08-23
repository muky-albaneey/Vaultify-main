# accounts/storages.py
from storages.backends.s3boto3 import S3Boto3Storage

class MediaRootS3Boto3Storage(S3Boto3Storage):
    location = "media"            # prefix inside the bucket
    default_acl = None            # use bucket policy
