from __future__ import annotations

import os
import uuid
from typing import Optional

import boto3
from botocore.client import Config


def _required(name: str) -> str:
    v = os.getenv(name, "").strip()
    if not v:
        raise RuntimeError(f"{name} is not set")
    return v


def _spaces_client():
    key = _required("DO_SPACES_KEY")
    secret = _required("DO_SPACES_SECRET")
    endpoint = _required("DO_SPACES_ENDPOINT")

    return boto3.client(
        "s3",
        region_name=os.getenv("DO_SPACES_REGION", "fra1"),
        endpoint_url=endpoint,
        aws_access_key_id=key,
        aws_secret_access_key=secret,
        config=Config(signature_version="s3v4"),
    )


def upload_bytes_to_spaces(
    *,
    content: bytes,
    content_type: str,
    key_prefix: str = "content",
    filename_ext: str = "png",
) -> str:
    """
    Uploads bytes to DigitalOcean Spaces and returns PUBLIC URL.
    """
    bucket = _required("DO_SPACES_BUCKET")
    public_base = _required("DO_SPACES_PUBLIC_BASE").rstrip("/")

    obj_key = f"{key_prefix}/{uuid.uuid4().hex}.{filename_ext.lstrip('.')}"
    client = _spaces_client()

    client.put_object(
        Bucket=bucket,
        Key=obj_key,
        Body=content,
        ACL="public-read",
        ContentType=content_type,
    )

    return f"{public_base}/{obj_key}"
