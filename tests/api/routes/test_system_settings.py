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
        "model_name": "",
        "api_key_configured": False,
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
        "endpoint_url": "https://ai.example.test/v1/chat/completions",
        "model_name": "vision-model",
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


KEY_URL = f"{settings.API_V1_STR}/api-keys/integrations/vision-inference"


def test_token_is_write_only_and_endpoint_bound(client, superuser_token_headers, db):
    payload = {
        "endpoint_url": "https://ai.example.test/v1/chat/completions",
        "model_name": "vision-model",
    }
    assert (
        client.put(URL, headers=superuser_token_headers, json=payload).status_code
        == 200
    )
    key_body = {
        "endpoint_url": payload["endpoint_url"],
        "api_key": "test-only-integration-token",
    }
    response = client.put(KEY_URL, headers=superuser_token_headers, json=key_body)
    assert response.status_code == 200 and response.json()["configured"] is True
    assert key_body["api_key"] not in response.text
    stored = db.get(AutolabelSettings, 1)
    assert (
        stored.api_key_encrypted and key_body["api_key"] not in stored.api_key_encrypted
    )
    cipher = stored.api_key_encrypted
    assert (
        "api_key_encrypted"
        not in client.get(URL, headers=superuser_token_headers).json()
    )
    runtime = client.get(URL + "/runtime", headers=superuser_token_headers)
    assert runtime.json()["api_key_encrypted"] == cipher
    assert key_body["api_key"] not in runtime.text
    assert (
        client.put(URL, headers=superuser_token_headers, json=payload).json()[
            "api_key_configured"
        ]
        is True
    )
    assert (
        client.put(
            KEY_URL,
            headers=superuser_token_headers,
            json={"endpoint_url": payload["endpoint_url"]},
        ).json()["configured"]
        is True
    )
    payload["endpoint_url"] = "https://other.example.test/v1/chat/completions"
    assert (
        client.put(URL, headers=superuser_token_headers, json=payload).json()[
            "api_key_configured"
        ]
        is False
    )
    assert (
        client.put(KEY_URL, headers=superuser_token_headers, json=key_body).status_code
        == 409
    )


def test_token_clear_and_https_required(client, superuser_token_headers):
    endpoint = "https://ai.example.test/v1/chat/completions"
    client.put(URL, headers=superuser_token_headers, json={"endpoint_url": endpoint})
    assert (
        client.put(
            KEY_URL,
            headers=superuser_token_headers,
            json={"endpoint_url": endpoint, "api_key": "test-only-token"},
        ).status_code
        == 200
    )
    assert (
        client.put(
            KEY_URL,
            headers=superuser_token_headers,
            json={"endpoint_url": endpoint, "clear_api_key": True},
        ).json()["configured"]
        is False
    )
    endpoint = "http://ai.example.test/v1/chat/completions"
    client.put(URL, headers=superuser_token_headers, json={"endpoint_url": endpoint})
    response = client.put(
        KEY_URL,
        headers=superuser_token_headers,
        json={"endpoint_url": endpoint, "api_key": "test-only-token"},
    )
    assert response.status_code == 422 and "test-only-token" not in response.text


def test_integration_keys_require_admin(client, normal_user_token_headers):
    assert client.get(KEY_URL).status_code == 401
    assert client.get(KEY_URL, headers=normal_user_token_headers).status_code == 403
    assert (
        client.put(
            KEY_URL,
            headers=normal_user_token_headers,
            json={"endpoint_url": "https://example.test"},
        ).status_code
        == 403
    )


def test_runtime_credentials_require_superuser(client, normal_user_token_headers):
    assert client.get(URL + "/runtime").status_code == 401
    assert (
        client.get(URL + "/runtime", headers=normal_user_token_headers).status_code
        == 403
    )
