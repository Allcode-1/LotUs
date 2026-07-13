from functools import lru_cache
from typing import BinaryIO, Any

import boto3
from botocore.config import Config
from botocore.exceptions import BotoCoreError, ClientError, NoCredentialsError

from app.core.config import settings


class StorageError(RuntimeError):
    def __init__(self, message: str) -> None:
        self.message = message
        super().__init__(message)


def _storage_client_kwargs() -> dict[str, Any]:
    if not settings.s3_bucket:
        raise StorageError("S3_BUCKET is not configured")

    kwargs: dict[str, Any] = {
        "region_name": settings.s3_region,
    }

    if settings.s3_endpoint_url:
        kwargs["endpoint_url"] = settings.s3_endpoint_url

    if settings.s3_access_key_id and settings.s3_secret_access_key:
        kwargs["aws_access_key_id"] = settings.s3_access_key_id
        kwargs["aws_secret_access_key"] = settings.s3_secret_access_key

    if settings.s3_force_path_style:
        kwargs["config"] = Config(s3={"addressing_style": "path"})

    return kwargs


@lru_cache
def get_s3_client():
    return boto3.client("s3", **_storage_client_kwargs())


def upload_fileobj(
    file_obj: BinaryIO,
    storage_key: str,
    content_type: str,
) -> None:
    try:
        get_s3_client().upload_fileobj(
            file_obj,
            settings.s3_bucket,
            storage_key,
            ExtraArgs={"ContentType": content_type},
        )
    except (BotoCoreError, ClientError, NoCredentialsError) as error:
        raise StorageError(f"Failed to upload object: {storage_key}") from error


def delete_object(storage_key: str) -> None:
    try:
        get_s3_client().delete_object(
            Bucket=settings.s3_bucket,
            Key=storage_key,
        )
    except (BotoCoreError, ClientError, NoCredentialsError) as error:
        raise StorageError(f"Failed to delete object: {storage_key}") from error


def create_presigned_url(storage_key: str) -> str:
    try:
        return get_s3_client().generate_presigned_url(
            "get_object",
            Params={
                "Bucket": settings.s3_bucket,
                "Key": storage_key,
            },
            ExpiresIn=settings.s3_presigned_url_expire_seconds,
        )
    except (BotoCoreError, ClientError, NoCredentialsError) as error:
        raise StorageError(f"Failed to create presigned URL: {storage_key}") from error
