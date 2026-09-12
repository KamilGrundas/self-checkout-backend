from fastapi.testclient import TestClient
from sqlmodel import Session, select

from app.core.config import settings
from app.models import ApiKey
from tests.utils.checkout_counter import create_random_checkout_counter_with_key


def test_create_checkout_counter_returns_its_key_once(
    client: TestClient, superuser_token_headers: dict[str, str], db: Session
) -> None:
    response = client.post(
        f"{settings.API_V1_STR}/checkout-counters/",
        headers=superuser_token_headers,
        json={"name": "Main checkout"},
    )

    assert response.status_code == 200
    content = response.json()
    assert content["name"] == "Main checkout"
    assert content["api_key"].startswith("sck_")
    assert "password" not in content
    row = db.exec(select(ApiKey).where(ApiKey.counter_id == content["id"])).one()
    assert row.key_hash != content["api_key"]
    assert row.purpose == "checkout_counter"


def test_counter_key_reads_catalog_but_not_admin_resources(
    client: TestClient, db: Session
) -> None:
    _, key = create_random_checkout_counter_with_key(db)
    headers = {"X-API-Key": key}

    assert (
        client.get(f"{settings.API_V1_STR}/products/", headers=headers).status_code
        == 200
    )
    assert (
        client.get(f"{settings.API_V1_STR}/categories/", headers=headers).status_code
        == 200
    )
    assert (
        client.get(
            f"{settings.API_V1_STR}/checkout-counters/", headers=headers
        ).status_code
        == 403
    )
    assert (
        client.get(f"{settings.API_V1_STR}/users/", headers=headers).status_code == 403
    )


def test_rotate_counter_key_revokes_the_previous_key(
    client: TestClient, superuser_token_headers: dict[str, str], db: Session
) -> None:
    counter, old_key = create_random_checkout_counter_with_key(db)
    response = client.post(
        f"{settings.API_V1_STR}/checkout-counters/{counter.id}/api-key/rotate",
        headers=superuser_token_headers,
    )

    assert response.status_code == 200
    new_key = response.json()["api_key"]
    assert new_key != old_key
    assert (
        client.get(
            f"{settings.API_V1_STR}/products/", headers={"X-API-Key": old_key}
        ).status_code
        == 401
    )
    assert (
        client.get(
            f"{settings.API_V1_STR}/products/", headers={"X-API-Key": new_key}
        ).status_code
        == 200
    )


def test_admin_updates_counter_settings(
    client: TestClient, superuser_token_headers: dict[str, str], db: Session
) -> None:
    counter, _ = create_random_checkout_counter_with_key(db)
    response = client.put(
        f"{settings.API_V1_STR}/checkout-counters/{counter.id}",
        headers=superuser_token_headers,
        json={"name": "Updated checkout", "ml_mode": "on", "language": "en"},
    )

    assert response.status_code == 200
    assert response.json()["name"] == "Updated checkout"
    assert response.json()["ml_mode"] == "on"
