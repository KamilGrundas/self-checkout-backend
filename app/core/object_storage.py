import json
import mimetypes
import uuid
from functools import lru_cache
from io import BytesIO
from pathlib import Path
from urllib.parse import quote

from minio import Minio
from PIL import Image

from app.core.config import settings

THUMBNAIL_SIZE = 250


@lru_cache
def get_minio_client() -> Minio:
    return Minio(
        settings.MINIO_ENDPOINT,
        access_key=settings.MINIO_ACCESS_KEY,
        secret_key=settings.MINIO_SECRET_KEY,
        secure=settings.MINIO_USE_SSL,
    )


def ensure_bucket_exists() -> None:
    client = get_minio_client()
    if not client.bucket_exists(settings.MINIO_BUCKET_NAME):
        client.make_bucket(settings.MINIO_BUCKET_NAME)
    client.set_bucket_policy(
        settings.MINIO_BUCKET_NAME,
        json.dumps(
            {
                "Version": "2012-10-17",
                "Statement": [
                    {
                        "Effect": "Allow",
                        "Principal": {"AWS": ["*"]},
                        "Action": ["s3:GetObject"],
                        "Resource": [f"arn:aws:s3:::{settings.MINIO_BUCKET_NAME}/*"],
                    }
                ],
            }
        ),
    )


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
    base_url = settings.MINIO_PUBLIC_URL.rstrip("/")
    return f"{base_url}/{settings.MINIO_BUCKET_NAME}/{quote(object_name, safe='/')}"


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
    client = get_minio_client()
    client.put_object(
        bucket_name=settings.MINIO_BUCKET_NAME,
        object_name=object_name,
        data=BytesIO(data),
        length=len(data),
        content_type=content_type,
    )
    return object_name


def store_product_thumbnail(*, product_id: uuid.UUID, data: bytes) -> str:
    ensure_bucket_exists()
    thumbnail_data = _make_thumbnail(data)
    object_name = f"products/{product_id}/thumbnail.webp"
    client = get_minio_client()
    client.put_object(
        bucket_name=settings.MINIO_BUCKET_NAME,
        object_name=object_name,
        data=BytesIO(thumbnail_data),
        length=len(thumbnail_data),
        content_type="image/webp",
    )
    return object_name
