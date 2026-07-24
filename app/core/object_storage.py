import mimetypes
import uuid
from functools import lru_cache
from io import BytesIO
from pathlib import Path
from typing import Any
from urllib.parse import quote

import boto3
from botocore.config import Config
from botocore.exceptions import ClientError
from PIL import Image

from app.core.config import settings

THUMBNAIL_SIZE = 250


class S3ObjectStorage:
    def __init__(self, client: Any, bucket: str, create_bucket: bool) -> None:
        self.client = client
        self.bucket = bucket
        self.create_bucket = create_bucket

    def ensure_bucket_exists(self) -> None:
        try:
            self.client.head_bucket(Bucket=self.bucket)
            return
        except ClientError as exc:
            status = exc.response.get("ResponseMetadata", {}).get("HTTPStatusCode")
            if status not in {400, 404}:
                raise
        if not self.create_bucket:
            raise RuntimeError(
                f"S3 bucket {self.bucket!r} is unavailable and S3_CREATE_BUCKETS=false"
            )
        kwargs: dict[str, object] = {"Bucket": self.bucket}
        if settings.S3_REGION != "us-east-1":
            kwargs["CreateBucketConfiguration"] = {
                "LocationConstraint": settings.S3_REGION
            }
        self.client.create_bucket(**kwargs)

    def put(self, object_name: str, data: bytes, content_type: str) -> None:
        self.client.put_object(
            Bucket=self.bucket,
            Key=object_name,
            Body=data,
            ContentType=content_type,
        )

    def get(self, object_name: str) -> tuple[bytes, str]:
        try:
            response = self.client.get_object(Bucket=self.bucket, Key=object_name)
        except ClientError as exc:
            status = exc.response.get("ResponseMetadata", {}).get("HTTPStatusCode")
            code = exc.response.get("Error", {}).get("Code")
            if status == 404 or code in {"NoSuchKey", "NotFound"}:
                raise ObjectNotFoundError(object_name) from exc
            raise
        body = response["Body"]
        try:
            data = body.read()
        finally:
            body.close()
        return data, response.get("ContentType") or "application/octet-stream"


class ObjectNotFoundError(Exception):
    pass


@lru_cache
def get_object_storage() -> S3ObjectStorage:
    config = Config(
        region_name=settings.S3_REGION,
        connect_timeout=settings.S3_CONNECT_TIMEOUT,
        read_timeout=settings.S3_READ_TIMEOUT,
        retries={"max_attempts": settings.S3_MAX_RETRIES, "mode": "standard"},
        s3={
            "addressing_style": ("path" if settings.S3_FORCE_PATH_STYLE else "virtual")
        },
    )
    client = boto3.client(
        "s3",
        endpoint_url=str(settings.S3_ENDPOINT_URL),
        region_name=settings.S3_REGION,
        aws_access_key_id=settings.S3_ACCESS_KEY_ID,
        aws_secret_access_key=settings.S3_SECRET_ACCESS_KEY,
        aws_session_token=settings.S3_SESSION_TOKEN,
        use_ssl=settings.S3_USE_SSL,
        verify=settings.S3_VERIFY_TLS,
        config=config,
    )
    if settings.S3_BUCKET is None:
        raise RuntimeError("S3_BUCKET is required")
    return S3ObjectStorage(client, settings.S3_BUCKET, settings.S3_CREATE_BUCKETS)


def ensure_bucket_exists() -> None:
    get_object_storage().ensure_bucket_exists()


def _get_object_name(
    product_id: uuid.UUID, filename: str | None, content_type: str
) -> str:
    suffix = Path(filename or "").suffix
    if not suffix:
        suffix = mimetypes.guess_extension(content_type) or ""
    return f"products/{product_id}/{uuid.uuid4()}{suffix.lower()}"


def _make_thumbnail(data: bytes) -> bytes:
    with Image.open(BytesIO(data)) as source:
        img: Image.Image = source.convert("RGB")
        w, h = img.size
        side = min(w, h)
        left = (w - side) // 2
        top = (h - side) // 2
        img = img.crop((left, top, left + side, top + side))
        img = img.resize((THUMBNAIL_SIZE, THUMBNAIL_SIZE), Image.Resampling.LANCZOS)
        out = BytesIO()
        img.save(out, format="WEBP", quality=85)
        return out.getvalue()


def public_url(object_name: str) -> str:
    if settings.BACKEND_PUBLIC_URL is None:
        raise RuntimeError("BACKEND_PUBLIC_URL is required")
    base_url = str(settings.BACKEND_PUBLIC_URL).rstrip("/")
    encoded_name = quote(object_name, safe="/")
    return f"{base_url}{settings.API_V1_STR}/products/object-storage/{encoded_name}"


def read_product_object(object_name: str) -> tuple[bytes, str]:
    return get_object_storage().get(object_name)


def store_product_image(
    *,
    product_id: uuid.UUID,
    filename: str | None,
    content_type: str,
    data: bytes,
) -> str:
    ensure_bucket_exists()
    object_name = _get_object_name(
        product_id=product_id, filename=filename, content_type=content_type
    )
    get_object_storage().put(object_name, data, content_type)
    return object_name


def store_product_thumbnail(*, product_id: uuid.UUID, data: bytes) -> str:
    ensure_bucket_exists()
    thumbnail_data = _make_thumbnail(data)
    object_name = f"products/{product_id}/thumbnail.webp"
    get_object_storage().put(object_name, thumbnail_data, "image/webp")
    return object_name
