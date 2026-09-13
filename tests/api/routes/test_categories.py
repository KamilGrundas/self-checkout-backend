import uuid

from fastapi.testclient import TestClient
from sqlmodel import Session

from app.core.config import settings
from app.models import DEFAULT_CATEGORY_KEY
from tests.utils.category import create_random_category


def test_read_categories(
    client: TestClient, superuser_token_headers: dict[str, str]
) -> None:
    response = client.get(
        f"{settings.API_V1_STR}/categories/", headers=superuser_token_headers
    )
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


def test_category_names_follow_the_selected_language(
    client: TestClient, superuser_token_headers: dict[str, str]
) -> None:
    created = client.post(
        f"{settings.API_V1_STR}/categories/?language=pl",
        headers=superuser_token_headers,
        json={"name": "Owoce"},
    )
    assert created.status_code == 200
    category = created.json()
    assert category["name_pl"] == "Owoce"
    assert category["name_en"] is None

    client.put(
        f"{settings.API_V1_STR}/categories/{category['id']}?language=pl",
        headers=superuser_token_headers,
        json={"name_en": "Fruit"},
    )
    response = client.get(
        f"{settings.API_V1_STR}/categories/?language=en",
        headers=superuser_token_headers,
    )
    updated = next(
        item for item in response.json()["data"] if item["id"] == category["id"]
    )
    assert updated["name"] == "Fruit"


def test_category_name_falls_back_to_the_other_translation(
    client: TestClient, superuser_token_headers: dict[str, str]
) -> None:
    created = client.post(
        f"{settings.API_V1_STR}/categories/?language=pl",
        headers=superuser_token_headers,
        json={"name": "Owoce"},
    )
    assert created.status_code == 200

    response = client.get(
        f"{settings.API_V1_STR}/categories/?language=en",
        headers=superuser_token_headers,
    )
    category = next(
        item for item in response.json()["data"] if item["id"] == created.json()["id"]
    )
    assert category["name"] == "Owoce"


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


def test_update_default_category_translation(
    client: TestClient, superuser_token_headers: dict[str, str]
) -> None:
    response = client.get(
        f"{settings.API_V1_STR}/categories/", headers=superuser_token_headers
    )
    default_category = next(
        category
        for category in response.json()["data"]
        if category["key"] == DEFAULT_CATEGORY_KEY
    )
    update_response = client.put(
        f"{settings.API_V1_STR}/categories/{default_category['id']}",
        headers=superuser_token_headers,
        json={"name_pl": "Inne"},
    )
    assert update_response.status_code == 200
    assert update_response.json()["name_pl"] == "Inne"


def test_delete_category_not_found(
    client: TestClient, superuser_token_headers: dict[str, str]
) -> None:
    response = client.delete(
        f"{settings.API_V1_STR}/categories/{uuid.uuid4()}",
        headers=superuser_token_headers,
    )
    assert response.status_code == 404
    assert response.json()["detail"] == "Category not found"
