import uuid

from fastapi.testclient import TestClient
from sqlmodel import Session

from app.core.config import settings
from app.models import DEFAULT_CATEGORY_KEY
from tests.utils.category import create_random_category


def test_read_categories(client: TestClient) -> None:
    response = client.get(f"{settings.API_V1_STR}/categories/")
    assert response.status_code == 200
    assert any(
        category["key"] == DEFAULT_CATEGORY_KEY for category in response.json()["data"]
    )


def test_create_category(
    client: TestClient, superuser_token_headers: dict[str, str]
) -> None:
    response = client.post(
        f"{settings.API_V1_STR}/categories/",
        headers=superuser_token_headers,
        json={"name": "Drinks"},
    )
    assert response.status_code == 200
    assert response.json()["name"] == "Drinks"
    assert response.json()["key"] == "drinks"


def test_update_category(
    client: TestClient, superuser_token_headers: dict[str, str], db: Session
) -> None:
    category = create_random_category(db)
    response = client.put(
        f"{settings.API_V1_STR}/categories/{category.id}",
        headers=superuser_token_headers,
        json={"name": "Updated"},
    )
    assert response.status_code == 200
    assert response.json()["name"] == "Updated"


def test_delete_category(
    client: TestClient, superuser_token_headers: dict[str, str], db: Session
) -> None:
    category = create_random_category(db)
    response = client.delete(
        f"{settings.API_V1_STR}/categories/{category.id}",
        headers=superuser_token_headers,
    )
    assert response.status_code == 200
    assert response.json()["message"] == "Category deleted successfully"


def test_update_default_category_forbidden(
    client: TestClient, superuser_token_headers: dict[str, str]
) -> None:
    response = client.get(f"{settings.API_V1_STR}/categories/")
    default_category = next(
        category for category in response.json()["data"] if category["key"] == DEFAULT_CATEGORY_KEY
    )
    update_response = client.put(
        f"{settings.API_V1_STR}/categories/{default_category['id']}",
        headers=superuser_token_headers,
        json={"name": "New name"},
    )
    assert update_response.status_code == 400
    assert update_response.json()["detail"] == "Default category cannot be renamed"


def test_delete_category_not_found(
    client: TestClient, superuser_token_headers: dict[str, str]
) -> None:
    response = client.delete(
        f"{settings.API_V1_STR}/categories/{uuid.uuid4()}",
        headers=superuser_token_headers,
    )
    assert response.status_code == 404
    assert response.json()["detail"] == "Category not found"
