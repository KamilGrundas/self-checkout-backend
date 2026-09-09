import httpx
import pytest

from app.core import autolabel_models
from app.core.autolabel_credentials import encrypt_api_key
from app.models import AutolabelSettings

ORIGINAL_CLIENT = httpx.Client
URL = "/api/v1/system-settings/autolabel/models"
ENDPOINT = "https://ai.example.test/v1/chat/completions"


def transport(monkeypatch, handler):
    monkeypatch.setattr(
        autolabel_models.httpx,
        "Client",
        lambda **kw: ORIGINAL_CLIENT(transport=httpx.MockTransport(handler), **kw),
    )


def setup(db):
    row = db.get(AutolabelSettings, 1) or AutolabelSettings()
    row.endpoint_url = ENDPOINT
    row.api_key_encrypted = encrypt_api_key("test-only-token", ENDPOINT)
    db.add(row)
    db.commit()


def test_lists_models_and_marks_active_without_exposing_key(
    client, superuser_token_headers, db, monkeypatch
):
    setup(db)

    def handler(request):
        assert request.headers["Authorization"] == "Bearer test-only-token"
        if request.url.path.endswith("/models"):
            return httpx.Response(
                200, json={"data": [{"id": "first"}, {"id": "loaded"}]}
            )
        return httpx.Response(
            200,
            json={
                "loaded": ["loaded"],
                "model_identifier": "loaded",
                "is_vision": True,
            },
        )

    transport(monkeypatch, handler)
    response = client.get(URL, headers=superuser_token_headers)
    assert response.status_code == 200
    assert response.json() == {
        "models": [
            {"id": "first", "loaded": False, "is_vision": None},
            {"id": "loaded", "loaded": True, "is_vision": True},
        ],
        "active_model": "loaded",
    }
    assert "test-only-token" not in response.text


@pytest.mark.parametrize("status", [302, 401, 500])
def test_discovery_errors_do_not_leak_upstream_body(
    client, superuser_token_headers, db, monkeypatch, status
):
    setup(db)
    calls = []

    def handler(request):
        calls.append(request.url)
        return httpx.Response(
            status,
            headers={"location": "https://other.example.test"},
            text="secret upstream response",
        )

    transport(monkeypatch, handler)
    response = client.get(URL, headers=superuser_token_headers)
    assert response.status_code == 502
    assert "secret upstream response" not in response.text
    assert len(calls) == 1


def test_model_list_requires_admin(client, normal_user_token_headers):
    assert client.get(URL).status_code == 401
    assert client.get(URL, headers=normal_user_token_headers).status_code == 403


def test_unloaded_model_is_not_reported_as_active(
    client, superuser_token_headers, db, monkeypatch
):
    setup(db)

    def handler(request):
        if request.url.path.endswith("/models"):
            return httpx.Response(200, json={"data": [{"id": "last-used"}]})
        return httpx.Response(
            200, json={"loaded": [], "model_identifier": "last-used", "is_vision": True}
        )

    transport(monkeypatch, handler)
    response = client.get(URL, headers=superuser_token_headers)
    assert response.status_code == 200
    assert response.json() == {
        "active_model": None,
        "models": [{"id": "last-used", "loaded": False, "is_vision": None}],
    }
