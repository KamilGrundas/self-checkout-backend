import uuid

from fastapi.testclient import TestClient
from sqlmodel import Session

from app.core.config import settings
from tests.utils.checkout_counter import create_random_checkout_counter_with_key
from tests.utils.product import create_random_product


def counter_headers(key: str) -> dict[str, str]:
    return {"X-API-Key": key}


def connect(client: TestClient, key: str, **payload: object) -> dict:
    response = client.post(
        f"{settings.API_V1_STR}/checkout-sessions/connect",
        headers=counter_headers(key),
        json=payload,
    )
    assert response.status_code == 200
    return response.json()


def test_connect_reuses_the_counter_open_session(
    client: TestClient, db: Session
) -> None:
    _, key = create_random_checkout_counter_with_key(db)
    first = connect(client, key)
    second = connect(client, key)

    assert first["id"] == second["id"]
    assert "client_id" not in first
    assert first["closed"] is False


def test_counter_key_cannot_access_another_counter_session(
    client: TestClient, db: Session
) -> None:
    _, first_key = create_random_checkout_counter_with_key(db)
    _, second_key = create_random_checkout_counter_with_key(db)
    first_session = connect(client, first_key)

    response = client.post(
        f"{settings.API_V1_STR}/checkout-sessions/{first_session['id']}/pay",
        headers=counter_headers(second_key),
        json={},
    )

    assert response.status_code == 403


def test_counter_key_updates_its_session_cart(client: TestClient, db: Session) -> None:
    _, key = create_random_checkout_counter_with_key(db)
    product = create_random_product(db)
    checkout_session = connect(client, key)

    response = client.put(
        f"{settings.API_V1_STR}/checkout-sessions/{checkout_session['id']}/cart",
        headers=counter_headers(key),
        json={
            "cart": [
                {
                    "product_id": str(product.id),
                    "name": product.name,
                    "unit": product.unit,
                    "price": 12.34,
                    "quantity": 2,
                    "quantity_label": "2 szt",
                    "line_total": 24.68,
                    "image_url": None,
                }
            ]
        },
    )

    assert response.status_code == 200
    assert response.json()["cart"][0]["product_id"] == str(product.id)


def test_payment_closes_session_and_next_connect_opens_a_new_one(
    client: TestClient, db: Session
) -> None:
    _, key = create_random_checkout_counter_with_key(db)
    first_session = connect(client, key)

    paid = client.post(
        f"{settings.API_V1_STR}/checkout-sessions/{first_session['id']}/pay",
        headers=counter_headers(key),
        json={},
    )

    assert paid.status_code == 200
    assert paid.json()["closed"] is True
    assert connect(client, key)["id"] != first_session["id"]


def test_counter_key_is_required(client: TestClient, db: Session) -> None:
    _, key = create_random_checkout_counter_with_key(db)
    assert (
        client.post(
            f"{settings.API_V1_STR}/checkout-sessions/connect", json={}
        ).status_code
        == 401
    )
    assert (
        client.post(
            f"{settings.API_V1_STR}/checkout-sessions/connect",
            headers={"X-API-Key": "sck_invalid"},
            json={},
        ).status_code
        == 401
    )
    assert key.startswith("sck_")


def test_checkout_key_check_binds_ml_uploads_to_its_counter(
    client: TestClient, db: Session
) -> None:
    _, first_key = create_random_checkout_counter_with_key(db)
    _, second_key = create_random_checkout_counter_with_key(db)
    first_session = connect(client, first_key)

    accepted = client.post(
        f"{settings.API_V1_STR}/login/checkout-key/check",
        headers=counter_headers(first_key),
        params={"scope": "ml:invoke", "checkout_session_id": first_session["id"]},
    )
    rejected = client.post(
        f"{settings.API_V1_STR}/login/checkout-key/check",
        headers=counter_headers(second_key),
        params={"scope": "ml:invoke", "checkout_session_id": first_session["id"]},
    )

    assert accepted.status_code == 200
    assert uuid.UUID(accepted.json()["counter_id"])
    assert rejected.status_code == 403
