"""VERIDEX API - Storage (MinIO)"""
import io

import structlog
from minio import Minio

from app.core.config import get_settings

logger = structlog.get_logger()
settings = get_settings()


def get_minio_client() -> Minio:
    return Minio(
        settings.MINIO_ENDPOINT,
        access_key=settings.MINIO_ACCESS_KEY,
        secret_key=settings.MINIO_SECRET_KEY,
        secure=settings.MINIO_USE_SSL,
    )


def ensure_bucket(client: Minio, bucket_name: str):
    if not client.bucket_exists(bucket_name):
        client.make_bucket(bucket_name)
        logger.info("bucket_created", bucket=bucket_name)


def upload_file(bucket_name: str, object_name: str, data: bytes, content_type: str) -> str:
    client = get_minio_client()
    ensure_bucket(client, bucket_name)
    data_stream = io.BytesIO(data)
    client.put_object(
        bucket_name,
        object_name,
        data_stream,
        length=len(data),
        content_type=content_type,
    )
    logger.info("file_uploaded", bucket=bucket_name, object=object_name)
    return f"{bucket_name}/{object_name}"


def download_file(bucket_name: str, object_name: str) -> bytes:
    client = get_minio_client()
    response = client.get_object(bucket_name, object_name)
    data = response.read()
    response.close()
    response.release_conn()
    return data


def delete_file(bucket_name: str, object_name: str):
    client = get_minio_client()
    client.remove_object(bucket_name, object_name)
    logger.info("file_deleted", bucket=bucket_name, object=object_name)
