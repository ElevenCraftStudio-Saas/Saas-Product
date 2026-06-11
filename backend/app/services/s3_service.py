import boto3
import os
import logging
from botocore.exceptions import ClientError
from typing import Optional

logger = logging.getLogger("wedfind.s3")

class S3Service:
    def __init__(self):
        self.bucket_name = os.getenv("AWS_BUCKET_NAME")
        self.region = os.getenv("AWS_REGION")
        self.s3_client = boto3.client(
            's3',
            aws_access_key_id=os.getenv("AWS_ACCESS_KEY_ID"),
            aws_secret_access_key=os.getenv("AWS_SECRET_ACCESS_KEY"),
            region_name=self.region
        )
        # Surface effective config at startup (no secrets).
        logger.info(
            "S3Service init: bucket=%s region=%s creds_present=%s",
            self.bucket_name, self.region, bool(os.getenv("AWS_ACCESS_KEY_ID")),
        )

    def upload_file(self, file_content, object_name: str, content_type: Optional[str] = None):
        try:
            extra_args = {}
            if content_type:
                extra_args['ContentType'] = content_type

            self.s3_client.put_object(
                Bucket=self.bucket_name,
                Key=object_name,
                Body=file_content,
                **extra_args
            )
            logger.info("S3 upload OK: key=%s bucket=%s", object_name, self.bucket_name)
            return True
        # Broadened from ClientError to Exception: NoCredentialsError,
        # EndpointConnectionError, ParamValidationError were previously
        # uncaught/unlogged and silently 500'd or bubbled.
        except Exception as e:
            logger.exception(
                "S3 upload FAILED: key=%s bucket=%s err=%s", object_name, self.bucket_name, e
            )
            return False

    def delete_file(self, object_name: str):
        try:
            self.s3_client.delete_object(Bucket=self.bucket_name, Key=object_name)
            return True
        except ClientError as e:
            print(f"S3 Delete Error: {e}")
            return False

    def generate_presigned_url(self, object_name: str, expiration: int = 3600):
        try:
            url = self.s3_client.generate_presigned_url(
                'get_object',
                Params={'Bucket': self.bucket_name, 'Key': object_name},
                ExpiresIn=expiration
            )
            return url
        except ClientError as e:
            print(f"S3 Presigned URL Error: {e}")
            return None

    def file_exists(self, object_name: str):
        try:
            self.s3_client.head_object(Bucket=self.bucket_name, Key=object_name)
            return True
        except ClientError:
            return False

    def download_to_temp(self, object_name: str, local_path: str):
        try:
            self.s3_client.download_file(self.bucket_name, object_name, local_path)
            return True
        except ClientError as e:
            print(f"S3 Download Error: {e}")
            return False

s3_service = S3Service()
