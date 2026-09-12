import uuid

import pytest
from fastapi.testclient import TestClient

ID = str(uuid.uuid4())


@pytest.mark.parametrize(
    "method,path",
    [
        ("GET", "/users/"),
        ("POST", "/users/"),
        ("GET", f"/users/{ID}"),
        ("PATCH", f"/users/{ID}"),
        ("DELETE", f"/users/{ID}"),
        ("PATCH", "/users/me"),
        ("PATCH", "/users/me/password"),
        ("DELETE", "/users/me"),
        ("GET", "/items/"),
        ("POST", "/items/"),
        ("GET", f"/items/{ID}"),
        ("PUT", f"/items/{ID}"),
        ("DELETE", f"/items/{ID}"),
        ("POST", "/products/"),
        ("PUT", f"/products/{ID}"),
        ("DELETE", f"/products/{ID}"),
        ("POST", f"/products/{ID}/image"),
        ("POST", "/categories/"),
        ("PUT", f"/categories/{ID}"),
        ("DELETE", f"/categories/{ID}"),
        ("GET", "/checkout-counters/"),
        ("POST", "/checkout-counters/"),
        ("PUT", f"/checkout-counters/{ID}"),
        ("DELETE", f"/checkout-counters/{ID}"),
        ("GET", "/checkout-sessions/active"),
        ("GET", "/system-settings/autolabel"),
        ("GET", "/vision-inference-integrations/"),
        ("POST", "/vision-inference-integrations/"),
        ("GET", "/api-keys/"),
        ("POST", "/api-keys/"),
        ("DELETE", f"/api-keys/{ID}"),
        ("POST", "/utils/test-email/"),
    ],
)
def test_catalog_reader_cannot_access_other_resources(
    client: TestClient,
    normal_user_token_headers: dict[str, str],
    method: str,
    path: str,
) -> None:
    response = client.request(
        method, "/api/v1" + path, headers=normal_user_token_headers, json={}
    )
    assert response.status_code == 403, (method, path, response.status_code)


def test_catalog_reader_can_read_catalog_and_session_identity(
    client: TestClient, normal_user_token_headers: dict[str, str]
) -> None:
    for path in ["/products/", "/categories/", "/users/me"]:
        assert (
            client.get("/api/v1" + path, headers=normal_user_token_headers).status_code
            == 200
        )
