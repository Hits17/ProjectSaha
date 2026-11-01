"""
S3-compatible storage client wrapping boto3.
Points to MinIO in dev; swap endpoint/credentials in .env for Azure Blob (S3-compat) in prod.
"""

import aioboto3
from contextlib import asynccontextmanager
from app.core.config import settings


def _make_session():
    return aioboto3.Session(
        aws_access_key_id=settings.MINIO_ACCESS_KEY,
        aws_secret_access_key=settings.MINIO_SECRET_KEY,
    )


@asynccontextmanager
async def _s3_client():
    session = _make_session()
    endpoint = f"{'https' if settings.MINIO_SECURE else 'http'}://{settings.MINIO_ENDPOINT}"
    async with session.client(
        "s3",
        endpoint_url=endpoint,
    ) as client:
        yield client


async def ensure_bucket_exists() -> None:
    async with _s3_client() as s3:
        try:
            await s3.head_bucket(Bucket=settings.MINIO_BUCKET)
        except Exception:
            await s3.create_bucket(Bucket=settings.MINIO_BUCKET)


async def upload_file(key: str, data: bytes, content_type: str = "application/octet-stream") -> str:
    async with _s3_client() as s3:
        await s3.put_object(
            Bucket=settings.MINIO_BUCKET,
            Key=key,
            Body=data,
            ContentType=content_type,
        )
    return key


async def generate_presigned_url(key: str, expires_in: int = 3600) -> str:
    async with _s3_client() as s3:
        url = await s3.generate_presigned_url(
            "get_object",
            Params={"Bucket": settings.MINIO_BUCKET, "Key": key},
            ExpiresIn=expires_in,
        )
    return url


async def delete_file(key: str) -> None:
    async with _s3_client() as s3:
        await s3.delete_object(Bucket=settings.MINIO_BUCKET, Key=key)


async def ping() -> bool:
    try:
        async with _s3_client() as s3:
            await s3.list_buckets()
        return True
    except Exception:
        return False
