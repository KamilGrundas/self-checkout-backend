import uuid
from decimal import Decimal

from fastapi.testclient import TestClient
from sqlmodel import Session

from app.core import object_storage
from app.core.config import settings
from app.models import DEFAULT_CATEGORY_KEY
from tests.utils.category import create_random_category
from tests.utils.product import create_random_product


def test_create_product(
    client: TestClient, superuser_token_headers: dict[str, str]
) -> None:
    data = {"name": "Apple", "price": "4.99", "unit": "kg", "image_url": None}
    response = client.post(
        f"{settings.API_V1_STR}/products/",
        headers=superuser_token_headers,
        json=data,
    )
    assert response.status_code == 200
    content = response.json()
    assert content["name"] == data["name"]
    assert content["price"] == data["price"]
    assert content["unit"] == data["unit"]
    assert content["image_url"] is None
    assert content["category_key"] == DEFAULT_CATEGORY_KEY
    assert "id" in content


def test_create_product_not_enough_permissions(
    client: TestClient, normal_user_token_headers: dict[str, str]
) -> None:
    data = {"name": "Apple", "price": "4.99", "unit": "kg", "image_url": None}
    response = client.post(
        f"{settings.API_V1_STR}/products/",
        headers=normal_user_token_headers,
        json=data,
    )
    assert response.status_code == 403
    assert response.json()["detail"] == "The user doesn't have enough privileges"


def test_read_product(client: TestClient, db: Session) -> None:
    product = create_random_product(db)
    response = client.get(f"{settings.API_V1_STR}/products/{product.id}")
    assert response.status_code == 200
    content = response.json()
    assert content["name"] == product.name
    assert Decimal(content["price"]) == product.price
    assert content["unit"] == product.unit
    assert content["id"] == str(product.id)
    assert content["category_key"] == DEFAULT_CATEGORY_KEY


def test_read_product_not_found(client: TestClient) -> None:
    response = client.get(f"{settings.API_V1_STR}/products/{uuid.uuid4()}")
    assert response.status_code == 404
    assert response.json()["detail"] == "Product not found"


def test_read_products(client: TestClient, db: Session) -> None:
    create_random_product(db)
    create_random_product(db)
    response = client.get(f"{settings.API_V1_STR}/products/")
    assert response.status_code == 200
    assert len(response.json()["data"]) >= 2


def test_update_product(
    client: TestClient, superuser_token_headers: dict[str, str], db: Session
) -> None:
    product = create_random_product(db)
    category = create_random_category(db)
    data = {
        "name": "Banana",
        "price": "9.99",
        "unit": "pcs",
        "image_url": None,
        "category_id": str(category.id),
    }
    response = client.put(
        f"{settings.API_V1_STR}/products/{product.id}",
        headers=superuser_token_headers,
        json=data,
    )
    assert response.status_code == 200
    content = response.json()
    assert content["name"] == data["name"]
    assert content["price"] == data["price"]
    assert content["unit"] == data["unit"]
    assert content["id"] == str(product.id)
    assert content["category_id"] == str(category.id)
    assert content["category_name"] == category.name


def test_update_product_not_found(
    client: TestClient, superuser_token_headers: dict[str, str]
) -> None:
    data = {"name": "Banana", "price": "9.99", "unit": "pcs"}
    response = client.put(
        f"{settings.API_V1_STR}/products/{uuid.uuid4()}",
        headers=superuser_token_headers,
        json=data,
    )
    assert response.status_code == 404
    assert response.json()["detail"] == "Product not found"


def test_upload_product_image(
    client: TestClient,
    superuser_token_headers: dict[str, str],
    db: Session,
    monkeypatch,
) -> None:
    product = create_random_product(db)
    image_object_name = "products/test.png"
    thumbnail_object_name = "products/test/thumbnail.webp"
    expected_url = "http://localhost:9000/product-images/products/test.png"
    expected_thumbnail_url = (
        "http://localhost:9000/product-images/products/test/thumbnail.webp"
    )

    def mock_store_product_image(
        *, product_id: uuid.UUID, filename: str | None, content_type: str, data: bytes
    ) -> str:
        assert product_id == product.id
        assert filename == "product.png"
        assert content_type == "image/png"
        assert data == b"fake-image"
        return image_object_name

    def mock_store_product_thumbnail(*, product_id: uuid.UUID, data: bytes) -> str:
        assert product_id == product.id
        assert data == b"fake-image"
        return thumbnail_object_name

    monkeypatch.setattr(object_storage, "store_product_image", mock_store_product_image)
    monkeypatch.setattr(
        object_storage, "store_product_thumbnail", mock_store_product_thumbnail
    )
    response = client.post(
        f"{settings.API_V1_STR}/products/{product.id}/image",
        headers=superuser_token_headers,
        files={"file": ("product.png", b"fake-image", "image/png")},
    )
    assert response.status_code == 200
    assert response.json()["image_url"] == expected_url
    assert response.json()["thumbnail_url"] == expected_thumbnail_url
    assert response.json()["category_key"] == DEFAULT_CATEGORY_KEY


def test_upload_product_image_invalid_file(
    client: TestClient, superuser_token_headers: dict[str, str], db: Session
) -> None:
    product = create_random_product(db)
    response = client.post(
        f"{settings.API_V1_STR}/products/{product.id}/image",
        headers=superuser_token_headers,
        files={"file": ("product.txt", b"not-image", "text/plain")},
    )
    assert response.status_code == 400
    assert response.json()["detail"] == "Invalid image file"


def test_delete_product(
    client: TestClient, superuser_token_headers: dict[str, str], db: Session
) -> None:
    product = create_random_product(db)
    response = client.delete(
        f"{settings.API_V1_STR}/products/{product.id}",
        headers=superuser_token_headers,
    )
    assert response.status_code == 200
    assert response.json()["message"] == "Product deleted successfully"


def test_delete_product_not_found(
    client: TestClient, superuser_token_headers: dict[str, str]
) -> None:
    response = client.delete(
        f"{settings.API_V1_STR}/products/{uuid.uuid4()}",
        headers=superuser_token_headers,
    )
    assert response.status_code == 404
    assert response.json()["detail"] == "Product not found"
