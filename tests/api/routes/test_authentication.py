import hashlib
import uuid
from datetime import UTC, datetime, timedelta

from fastapi.testclient import TestClient
from sqlmodel import Session

from app.models import ApiKey


def test_local_password_login(
    client: TestClient, superuser_token_headers: dict[str, str]
) -> None:
    assert (
        client.get("/api/v1/users/me", headers=superuser_token_headers).status_code
        == 200
    )


def test_anonymous_catalog_denied(client: TestClient) -> None:
    assert client.get("/api/v1/products/").status_code == 401
    assert client.get("/api/v1/categories/").status_code == 401


def test_key_scope_expiration_revocation(
    client: TestClient, db: Session, superuser_token_headers: dict[str, str]
) -> None:
    response = client.post(
        "/api/v1/api-keys/",
        headers=superuser_token_headers,
        json={"name": "test-reader", "role": "user"},
    )
    assert response.status_code == 201
    data = response.json()
    raw = data["key"]
    row = db.get(ApiKey, uuid.UUID(data["id"]))
    assert row and row.key_hash == hashlib.sha256(raw.encode()).hexdigest()
    assert (
        raw not in client.get("/api/v1/api-keys/", headers=superuser_token_headers).text
    )
    headers = {"X-API-Key": raw}
    assert client.get("/api/v1/products/", headers=headers).status_code == 200
    assert (
        client.post(
            "/api/v1/products/",
            headers=headers,
            json={"name": "x", "price": "1", "unit": "pcs"},
        ).status_code
        == 403
    )
    assert client.get("/api/v1/users/", headers=headers).status_code == 403
    assert (
        client.post(
            "/api/v1/login/api-key/check?scope=ml:invoke", headers=headers
        ).status_code
        == 403
    )
    row.expires_at = datetime.now(UTC) - timedelta(seconds=1)
    db.add(row)
    db.commit()
    assert client.get("/api/v1/products/", headers=headers).status_code == 401
    row.expires_at = datetime.now(UTC) + timedelta(days=1)
    db.add(row)
    db.commit()
    assert (
        client.delete(
            f"/api/v1/api-keys/{row.id}", headers=superuser_token_headers
        ).status_code
        == 200
    )
    assert client.get("/api/v1/products/", headers=headers).status_code == 401
