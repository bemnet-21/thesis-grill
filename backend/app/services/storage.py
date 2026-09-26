"""PDF storage abstraction — local filesystem or S3."""

import os
from pathlib import Path

from app.core.config import settings


import tempfile

def save_pdf(filename: str, content: bytes) -> str:
    """Persist a PDF and return the stored path/URI."""
    if settings.UPLOAD_BACKEND == "s3":
        return _save_to_s3(filename, content)
    return _save_to_local(filename, content)


def download_pdf(pdf_path: str) -> str:
    """Download a PDF (if S3) to a local temp file, or return the local path."""
    if pdf_path.startswith("s3://"):
        return _download_from_s3(pdf_path)
    return pdf_path


def _save_to_local(filename: str, content: bytes) -> str:
    upload_dir = Path(settings.UPLOAD_DIR)
    upload_dir.mkdir(parents=True, exist_ok=True)
    path = upload_dir / filename
    path.write_bytes(content)
    return str(path)


def _save_to_s3(filename: str, content: bytes) -> str:
    import boto3
    from botocore.config import Config

    endpoint = settings.S3_ENDPOINT_URL or None
    s3 = boto3.client(
        "s3",
        region_name=settings.AWS_REGION,
        endpoint_url=endpoint,
        config=Config(s3={"addressing_style": "path"}),
    )
    key = f"{settings.S3_PREFIX}{filename}"
    s3.put_object(Bucket=settings.S3_BUCKET, Key=key, Body=content)
    return f"s3://{settings.S3_BUCKET}/{key}"


def _download_from_s3(s3_uri: str) -> str:
    import boto3
    from botocore.config import Config

    parts = s3_uri.replace("s3://", "").split("/", 1)
    bucket = parts[0]
    key = parts[1]

    endpoint = settings.S3_ENDPOINT_URL or None
    s3 = boto3.client(
        "s3",
        region_name=settings.AWS_REGION,
        endpoint_url=endpoint,
        config=Config(s3={"addressing_style": "path"}),
    )

    fd, tmp_path = tempfile.mkstemp(suffix=".pdf")
    os.close(fd)

    s3.download_file(bucket, key, tmp_path)
    return tmp_path

