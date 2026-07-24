from io import BytesIO
from typing import Any

from botocore.exceptions import ClientError

from app.core.object_storage import S3ObjectStorage


class FakeS3Client:
    def __init__(self, bucket_exists: bool = True) -> None:
        self.bucket_exists = bucket_exists
        self.calls: list[tuple[str, dict[str, Any]]] = []

    def head_bucket(self, **kwargs: Any) -> None:
        self.calls.append(("head_bucket", kwargs))
        if not self.bucket_exists:
            raise ClientError(
                {
                    "Error": {"Code": "404", "Message": "Not Found"},
                    "ResponseMetadata": {"HTTPStatusCode": 404},
                },
                "HeadBucket",
            )

    def create_bucket(self, **kwargs: Any) -> None:
        self.calls.append(("create_bucket", kwargs))

    def put_object(self, **kwargs: Any) -> None:
        self.calls.append(("put_object", kwargs))

    def get_object(self, **kwargs: Any) -> dict[str, Any]:
        self.calls.append(("get_object", kwargs))
        return {"Body": BytesIO(b"image"), "ContentType": "image/jpeg"}


def test_put_preserves_content_type() -> None:
    client = FakeS3Client()
    storage = S3ObjectStorage(client, "images", create_bucket=False)  # type: ignore[arg-type]

    storage.put("products/one.jpg", b"image", "image/jpeg")

    assert client.calls == [
        (
            "put_object",
            {
                "Bucket": "images",
                "Key": "products/one.jpg",
                "Body": b"image",
                "ContentType": "image/jpeg",
            },
        )
    ]


def test_missing_bucket_is_created_only_when_enabled() -> None:
    client = FakeS3Client(bucket_exists=False)
    storage = S3ObjectStorage(client, "images", create_bucket=True)  # type: ignore[arg-type]

    storage.ensure_bucket_exists()

    assert client.calls[-1] == ("create_bucket", {"Bucket": "images"})


def test_missing_bucket_fails_when_creation_is_disabled() -> None:
    client = FakeS3Client(bucket_exists=False)
    storage = S3ObjectStorage(client, "images", create_bucket=False)  # type: ignore[arg-type]

    try:
        storage.ensure_bucket_exists()
    except RuntimeError as exc:
        assert "S3_CREATE_BUCKETS=false" in str(exc)
    else:
        raise AssertionError("missing bucket must fail")


def test_get_returns_object_body_and_content_type() -> None:
    client = FakeS3Client()
    storage = S3ObjectStorage(client, "images", create_bucket=False)  # type: ignore[arg-type]

    data, content_type = storage.get("products/one.jpg")

    assert data == b"image"
    assert content_type == "image/jpeg"
    assert client.calls == [
        (
            "get_object",
            {"Bucket": "images", "Key": "products/one.jpg"},
        )
    ]
