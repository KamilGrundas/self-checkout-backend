import uuid

from fastapi.testclient import TestClient
from sqlmodel import Session

from app.core.config import settings
from tests.utils.checkout_counter import create_random_checkout_counter


def test_create_checkout_counter(
    client: TestClient, superuser_token_headers: dict[str, str]
) -> None:
    data = {"name": "Main checkout", "password": "checkout-secret"}
    response = client.post(
        f"{settings.API_V1_STR}/checkout-counters/",
        headers=superuser_token_headers,
        json=data,
    )
    assert response.status_code == 200
    content = response.json()
    assert content["name"] == data["name"]
    assert "id" in content
    assert "password_hash" not in content


def test_read_checkout_counters(
    client: TestClient, superuser_token_headers: dict[str, str], db: Session
) -> None:
    create_random_checkout_counter(db)
    response = client.get(
        f"{settings.API_V1_STR}/checkout-counters/",
        headers=superuser_token_headers,
    )
    assert response.status_code == 200
    assert response.json()["count"] >= 1


def test_update_checkout_counter(
    client: TestClient, superuser_token_headers: dict[str, str], db: Session
) -> None:
    counter = create_random_checkout_counter(db)
    response = client.put(
        f"{settings.API_V1_STR}/checkout-counters/{counter.id}",
        headers=superuser_token_headers,
        json={"name": "Updated checkout", "password": "new-secret"},
    )
    assert response.status_code == 200
    assert response.json()["name"] == "Updated checkout"


def test_delete_checkout_counter(
    client: TestClient, superuser_token_headers: dict[str, str], db: Session
) -> None:
    counter = create_random_checkout_counter(db)
    response = client.delete(
        f"{settings.API_V1_STR}/checkout-counters/{counter.id}",
        headers=superuser_token_headers,
    )
    assert response.status_code == 200
    assert response.json()["message"] == "Checkout counter deleted successfully"


def test_update_checkout_counter_not_found(
    client: TestClient, superuser_token_headers: dict[str, str]
) -> None:
    response = client.put(
        f"{settings.API_V1_STR}/checkout-counters/{uuid.uuid4()}",
        headers=superuser_token_headers,
        json={"name": "Updated checkout"},
    )
    assert response.status_code == 404
    assert response.json()["detail"] == "Checkout counter not found"
