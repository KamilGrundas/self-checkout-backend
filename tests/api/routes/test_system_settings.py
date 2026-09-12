import uuid

import httpx

from app.core import autolabel_models
from app.models import VisionInferenceIntegration

URL = "/api/v1/vision-inference-integrations/"


def transport(monkeypatch, handler):
    original = httpx.Client
    monkeypatch.setattr(
        autolabel_models.httpx,
        "Client",
        lambda **kw: original(transport=httpx.MockTransport(handler), **kw),
    )


def create(client, headers, name="Vision one"):
    response = client.post(
        URL,
        headers=headers,
        json={
            "name": name,
            "endpoint_url": "https://ai.example.test/v1/chat/completions",
            "api_key": "test-only-integration-token",
        },
    )
    assert response.status_code == 201
    return response.json()


def test_create_is_write_only_and_supports_multiple_integrations(
    client, superuser_token_headers, db
):
    first = create(client, superuser_token_headers)
    create(client, superuser_token_headers, "Vision two")
    assert first["api_key_configured"] is True
    assert "test-only-integration-token" not in first
    assert len(client.get(URL, headers=superuser_token_headers).json()) == 2
    stored = db.get(VisionInferenceIntegration, uuid.UUID(first["id"]))
    assert stored.api_key_encrypted
    assert "test-only-integration-token" not in stored.api_key_encrypted


def test_model_selection_and_activation_enable_autolabel(
    client, superuser_token_headers, db
):
    integration = create(client, superuser_token_headers)
    integration_id = integration["id"]
    assert (
        client.post(
            f"{URL}{integration_id}/activate", headers=superuser_token_headers
        ).status_code
        == 409
    )
    assert (
        client.patch(
            f"{URL}{integration_id}",
            headers=superuser_token_headers,
            json={"model_name": "vision-model"},
        ).status_code
        == 200
    )
    activated = client.post(
        f"{URL}{integration_id}/activate", headers=superuser_token_headers
    )
    assert activated.status_code == 200 and activated.json()["active"] is True
    public = client.get(
        "/api/v1/system-settings/autolabel", headers=superuser_token_headers
    ).json()
    assert public["configured"] is True
    runtime = client.get(
        "/api/v1/system-settings/autolabel/runtime", headers=superuser_token_headers
    ).json()
    assert (
        runtime["api_key_encrypted"]
        == db.get(
            VisionInferenceIntegration, uuid.UUID(integration_id)
        ).api_key_encrypted
    )


def test_discovery_reports_loaded_model_without_leaking_key(
    client, superuser_token_headers, monkeypatch
):
    integration = create(client, superuser_token_headers)

    def handler(request):
        assert request.headers["Authorization"] == "Bearer test-only-integration-token"
        if request.url.path.endswith("/models"):
            return httpx.Response(200, json={"data": [{"id": "vision"}]})
        return httpx.Response(
            200,
            json={
                "loaded": ["vision"],
                "model_identifier": "vision",
                "is_vision": True,
            },
        )

    transport(monkeypatch, handler)
    response = client.get(
        f"{URL}{integration['id']}/models", headers=superuser_token_headers
    )
    assert response.status_code == 200
    assert response.json()["active_model"] == "vision"
    assert "test-only-integration-token" not in response.text


def test_integrations_require_administrator(client, normal_user_token_headers):
    assert client.get(URL).status_code == 401
    assert client.get(URL, headers=normal_user_token_headers).status_code == 403
