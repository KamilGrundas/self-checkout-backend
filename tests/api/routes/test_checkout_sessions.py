import uuid
from unittest.mock import AsyncMock, patch

from fastapi.testclient import TestClient
from sqlmodel import Session

from app.core.config import settings
from tests.utils.checkout_counter import create_random_checkout_counter
from tests.utils.product import create_random_product


def test_connect_checkout_session_reuses_open_session(
    client: TestClient, db: Session
) -> None:
    counter = create_random_checkout_counter(db)
    payload = {
        "counter_id": str(counter.id),
        "password": "secret-password",
        "client_id": "client-1",
    }

    first_response = client.post(
        f"{settings.API_V1_STR}/checkout-sessions/connect",
        json=payload,
    )
    second_response = client.post(
        f"{settings.API_V1_STR}/checkout-sessions/connect",
        json=payload,
    )

    assert first_response.status_code == 200
    assert second_response.status_code == 200
    assert first_response.json()["id"] == second_response.json()["id"]
    assert first_response.json()["closed"] is False
    assert first_response.json()["payment_status"] == "pending"


def test_connect_checkout_session_invalid_credentials(
    client: TestClient, db: Session
) -> None:
    counter = create_random_checkout_counter(db)
    response = client.post(
        f"{settings.API_V1_STR}/checkout-sessions/connect",
        json={
            "counter_id": str(counter.id),
            "password": "wrong-password",
            "client_id": "client-1",
        },
    )
    assert response.status_code == 403
    assert response.json()["detail"] == "Invalid checkout counter credentials"


def test_counter_settings_changes_apply_to_next_session(
    client: TestClient,
    superuser_token_headers: dict[str, str],
    db: Session,
) -> None:
    counter = create_random_checkout_counter(db)
    connect_payload = {
        "counter_id": str(counter.id),
        "password": "secret-password",
        "client_id": "settings-snapshot-client",
        "available_cameras": [
            {"device_id": "camera-1", "label": "Camera 1", "index": 0},
            {"device_id": "camera-2", "label": "Camera 2", "index": 1},
        ],
    }

    initial_update = client.put(
        f"{settings.API_V1_STR}/checkout-counters/{counter.id}",
        headers=superuser_token_headers,
        json={"scale_camera_device_id": None},
    )
    assert initial_update.status_code == 200
    first_connect = client.post(
        f"{settings.API_V1_STR}/checkout-sessions/connect",
        json=connect_payload,
    )
    assert first_connect.status_code == 200
    first_session = first_connect.json()
    assert first_session["counter_settings"]["scale_camera_device_id"] is None

    settings_update = client.put(
        f"{settings.API_V1_STR}/checkout-counters/{counter.id}",
        headers=superuser_token_headers,
        json={"scale_camera_device_id": "camera-2", "ml_mode": "on"},
    )
    assert settings_update.status_code == 200

    same_session = client.post(
        f"{settings.API_V1_STR}/checkout-sessions/connect",
        json=connect_payload,
    )
    assert same_session.status_code == 200
    assert same_session.json()["id"] == first_session["id"]
    assert same_session.json()["counter_settings"]["scale_camera_device_id"] is None
    assert same_session.json()["counter_settings"]["ml_mode"] == "off"

    paid = client.post(
        f"{settings.API_V1_STR}/checkout-sessions/{first_session['id']}/pay",
        json={
            "counter_id": str(counter.id),
            "password": "secret-password",
            "client_id": "settings-snapshot-client",
        },
    )
    assert paid.status_code == 200

    next_connect = client.post(
        f"{settings.API_V1_STR}/checkout-sessions/connect",
        json=connect_payload,
    )
    assert next_connect.status_code == 200
    assert next_connect.json()["id"] != first_session["id"]
    assert (
        next_connect.json()["counter_settings"]["scale_camera_device_id"]
        == "camera-2"
    )
    assert next_connect.json()["counter_settings"]["ml_mode"] == "on"


def test_update_checkout_session_cart(client: TestClient, db: Session) -> None:
    counter = create_random_checkout_counter(db)
    product = create_random_product(db)
    connect_response = client.post(
        f"{settings.API_V1_STR}/checkout-sessions/connect",
        json={
            "counter_id": str(counter.id),
            "password": "secret-password",
            "client_id": "client-cart",
        },
    )
    session_id = connect_response.json()["id"]
    payload = {
        "counter_id": str(counter.id),
        "password": "secret-password",
        "client_id": "client-cart",
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
        ],
    }

    response = client.put(
        f"{settings.API_V1_STR}/checkout-sessions/{session_id}/cart",
        json=payload,
    )

    assert response.status_code == 200
    assert response.json()["cart"][0]["product_id"] == str(product.id)
    assert response.json()["cart"][0]["quantity"] == 2


def test_pay_checkout_session_closes_session(client: TestClient, db: Session) -> None:
    counter = create_random_checkout_counter(db)
    connect_response = client.post(
        f"{settings.API_V1_STR}/checkout-sessions/connect",
        json={
            "counter_id": str(counter.id),
            "password": "secret-password",
            "client_id": "client-pay",
        },
    )
    session_id = connect_response.json()["id"]

    with patch(
        "app.api.routes.checkout_sessions.ws_manager.disconnect_clients",
        new_callable=AsyncMock,
    ) as disconnect_clients:
        response = client.post(
            f"{settings.API_V1_STR}/checkout-sessions/{session_id}/pay",
            json={
                "counter_id": str(counter.id),
                "password": "secret-password",
                "client_id": "client-pay",
            },
        )

    assert response.status_code == 200
    assert response.json()["closed"] is True
    assert response.json()["payment_status"] == "paid"
    disconnect_clients.assert_awaited_once_with(uuid.UUID(session_id))


def test_pay_checkout_session_requires_matching_client(
    client: TestClient, db: Session
) -> None:
    counter = create_random_checkout_counter(db)
    connect_response = client.post(
        f"{settings.API_V1_STR}/checkout-sessions/connect",
        json={
            "counter_id": str(counter.id),
            "password": "secret-password",
            "client_id": "client-pay-1",
        },
    )
    session_id = connect_response.json()["id"]

    response = client.post(
        f"{settings.API_V1_STR}/checkout-sessions/{session_id}/pay",
        json={
            "counter_id": str(counter.id),
            "password": "secret-password",
            "client_id": "client-pay-2",
        },
    )

    assert response.status_code == 403
    assert response.json()["detail"] == "Checkout session access denied"
