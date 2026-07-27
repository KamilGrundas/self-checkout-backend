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


def test_connection_reports_available_cameras(
    client: TestClient,
    superuser_token_headers: dict[str, str],
    db: Session,
) -> None:
    counter = create_random_checkout_counter(db)
    cameras = [
        {
            "device_id": "camera-scale",
            "label": "Scale camera",
            "index": 1,
        },
        {
            "device_id": "camera-shelf",
            "label": "Shelf camera",
            "index": 0,
        },
    ]

    connect_response = client.post(
        f"{settings.API_V1_STR}/checkout-sessions/connect",
        json={
            "counter_id": str(counter.id),
            "password": "secret-password",
            "client_id": "camera-report-client",
            "available_cameras": cameras,
        },
    )
    assert connect_response.status_code == 200

    counters_response = client.get(
        f"{settings.API_V1_STR}/checkout-counters/",
        headers=superuser_token_headers,
    )
    reported = next(
        item
        for item in counters_response.json()["data"]
        if item["id"] == str(counter.id)
    )
    assert reported["available_cameras"] == cameras
    assert reported["available_cameras_updated_at"] is not None


def test_failed_camera_discovery_preserves_last_successful_report(
    client: TestClient,
    superuser_token_headers: dict[str, str],
    db: Session,
) -> None:
    counter = create_random_checkout_counter(db)
    cameras = [
        {"device_id": "camera-1", "label": "Camera 1", "index": 0},
    ]
    connect_url = f"{settings.API_V1_STR}/checkout-sessions/connect"

    first_response = client.post(
        connect_url,
        json={
            "counter_id": str(counter.id),
            "password": "secret-password",
            "client_id": "camera-restart-client",
            "available_cameras": cameras,
            "camera_discovery_succeeded": True,
        },
    )
    failed_discovery_response = client.post(
        connect_url,
        json={
            "counter_id": str(counter.id),
            "password": "secret-password",
            "client_id": "camera-restart-client",
            "available_cameras": [],
            "camera_discovery_succeeded": False,
        },
    )

    assert first_response.status_code == 200
    assert failed_discovery_response.status_code == 200
    counters_response = client.get(
        f"{settings.API_V1_STR}/checkout-counters/",
        headers=superuser_token_headers,
    )
    reported = next(
        item
        for item in counters_response.json()["data"]
        if item["id"] == str(counter.id)
    )
    assert reported["available_cameras"] == cameras


def test_successful_empty_camera_discovery_clears_report(
    client: TestClient,
    superuser_token_headers: dict[str, str],
    db: Session,
) -> None:
    counter = create_random_checkout_counter(db)
    connect_url = f"{settings.API_V1_STR}/checkout-sessions/connect"
    base_payload = {
        "counter_id": str(counter.id),
        "password": "secret-password",
        "client_id": "camera-removal-client",
        "camera_discovery_succeeded": True,
    }

    first_response = client.post(
        connect_url,
        json={
            **base_payload,
            "available_cameras": [
                {"device_id": "camera-1", "label": "Camera 1", "index": 0}
            ],
        },
    )
    empty_response = client.post(
        connect_url,
        json={**base_payload, "available_cameras": []},
    )

    assert first_response.status_code == 200
    assert empty_response.status_code == 200
    counters_response = client.get(
        f"{settings.API_V1_STR}/checkout-counters/",
        headers=superuser_token_headers,
    )
    reported = next(
        item
        for item in counters_response.json()["data"]
        if item["id"] == str(counter.id)
    )
    assert reported["available_cameras"] == []


def test_counter_camera_selection_must_use_reported_device(
    client: TestClient,
    superuser_token_headers: dict[str, str],
    db: Session,
) -> None:
    counter = create_random_checkout_counter(db)
    client.post(
        f"{settings.API_V1_STR}/checkout-sessions/connect",
        json={
            "counter_id": str(counter.id),
            "password": "secret-password",
            "client_id": "camera-selection-client",
            "available_cameras": [
                {"device_id": "camera-1", "label": "Camera 1", "index": 0}
            ],
        },
    )

    accepted = client.put(
        f"{settings.API_V1_STR}/checkout-counters/{counter.id}",
        headers=superuser_token_headers,
        json={"scale_camera_device_id": "camera-1"},
    )
    rejected = client.put(
        f"{settings.API_V1_STR}/checkout-counters/{counter.id}",
        headers=superuser_token_headers,
        json={"scale_camera_device_id": "invented-camera"},
    )

    assert accepted.status_code == 200
    assert accepted.json()["scale_camera_device_id"] == "camera-1"
    assert rejected.status_code == 422


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
