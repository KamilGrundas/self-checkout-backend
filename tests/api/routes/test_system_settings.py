from fastapi.testclient import TestClient
from sqlmodel import Session

from app.core.config import settings
from app.models import AutolabelSettings

URL = f"{settings.API_V1_STR}/system-settings/autolabel"


def test_autolabel_settings_default_for_superuser(
    client: TestClient,
    superuser_token_headers: dict[str, str],
    db: Session,
) -> None:
    stored = db.get(AutolabelSettings, 1)
    if stored:
        db.delete(stored)
        db.commit()

    response = client.get(URL, headers=superuser_token_headers)

    assert response.status_code == 200
    assert response.json() == {
        "endpoint_url": None,
        "max_tokens": 512,
        "connect_timeout_seconds": 5,
        "read_timeout_seconds": 120,
        "configured": False,
        "updated_at": None,
    }


def test_autolabel_settings_update_singleton(
    client: TestClient,
    superuser_token_headers: dict[str, str],
    db: Session,
) -> None:
    payload = {
        "endpoint_url": "http://192.168.0.29:8088/v1/files/inference",
        "max_tokens": 768,
        "connect_timeout_seconds": 4,
        "read_timeout_seconds": 180,
    }

    first = client.put(URL, headers=superuser_token_headers, json=payload)
    second = client.put(
        URL,
        headers=superuser_token_headers,
        json={**payload, "max_tokens": 512},
    )

    assert first.status_code == 200
    assert second.status_code == 200
    assert second.json()["configured"] is True
    assert second.json()["max_tokens"] == 512
    assert db.get(AutolabelSettings, 1) is not None


def test_autolabel_settings_forbid_normal_user(
    client: TestClient,
    normal_user_token_headers: dict[str, str],
) -> None:
    assert client.get(URL, headers=normal_user_token_headers).status_code == 403
    assert (
        client.put(
            URL,
            headers=normal_user_token_headers,
            json={"endpoint_url": "http://example.test/inference"},
        ).status_code
        == 403
    )


def test_autolabel_settings_require_authentication(client: TestClient) -> None:
    assert client.get(URL).status_code == 401


def test_autolabel_settings_validate_url_and_parameters(
    client: TestClient,
    superuser_token_headers: dict[str, str],
) -> None:
    invalid_urls = (
        "ftp://example.test/inference",
        "http://user:password@example.test/inference",
        "https://example.test/inference#fragment",
        "not-a-url",
    )
    for endpoint_url in invalid_urls:
        response = client.put(
            URL,
            headers=superuser_token_headers,
            json={"endpoint_url": endpoint_url},
        )
        assert response.status_code == 422

    for field, value in (
        ("max_tokens", 0),
        ("max_tokens", 4097),
        ("connect_timeout_seconds", 0),
        ("read_timeout_seconds", 601),
    ):
        response = client.put(
            URL,
            headers=superuser_token_headers,
            json={"endpoint_url": "http://example.test/inference", field: value},
        )
        assert response.status_code == 422
