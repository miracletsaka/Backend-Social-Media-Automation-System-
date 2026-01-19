import os
import boto3

# ---------- S3 / DigitalOcean Spaces (S3-compatible) ----------

S3_BUCKET = os.getenv("S3_BUCKET_NAME")
S3_ENDPOINT = os.getenv("S3_ENDPOINT")
S3_PUBLIC_URL = os.getenv("S3_PUBLIC_URL")
S3_ACCESS_KEY = os.getenv("S3_ACCESS_KEY_ID")
S3_SECRET_KEY = os.getenv("S3_SECRET_ACCESS_KEY")

if not all([S3_BUCKET, S3_ENDPOINT, S3_PUBLIC_URL, S3_ACCESS_KEY, S3_SECRET_KEY]):
    raise RuntimeError("Missing S3 environment variables")

session = boto3.session.Session()

s3 = session.client(
    "s3",
    endpoint_url=S3_ENDPOINT,
    aws_access_key_id=S3_ACCESS_KEY,
    aws_secret_access_key=S3_SECRET_KEY,
)


def upload_bytes(
    *,
    data: bytes,
    key: str,
    content_type: str,
) -> str:
    """
    Upload raw bytes to S3 / DigitalOcean Spaces
    and return a PUBLIC URL.
    """

    s3.put_object(
        Bucket=S3_BUCKET,
        Key=key,
        Body=data,
        ACL="public-read",
        ContentType=content_type,
    )

    return f"{S3_PUBLIC_URL}/{key}"
