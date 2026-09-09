import hashlib
import uuid
from datetime import UTC, datetime, timedelta

import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import rsa
from fastapi import HTTPException
from fastapi.testclient import TestClient
from sqlmodel import Session, select

from app.core import oidc
from app.core.config import settings
from app.models import ApiKey, User


def test_exclusive_oidc_mode(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
    superuser_token_headers: dict[str, str],
) -> None:
    monkeypatch.setattr(settings, "AUTH_MODE", "oidc")
    assert (
        client.post(
            "/api/v1/login/access-token",
            data={"username": "a@example.com", "password": "irrelevant"},
        ).status_code
        == 403
    )
    assert (
        client.post(
            "/api/v1/users/signup",
            json={"email": "a@example.com", "password": "password123"},
        ).status_code
        == 403
    )
    monkeypatch.setattr(
        oidc, "discovery", lambda _: {"jwks_uri": "https://id.example/keys"}
    )
    assert (
        client.get("/api/v1/users/me", headers=superuser_token_headers).status_code
        == 401
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


def test_oidc_identity_and_live_groups(
    client: TestClient, db: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    oidc.cached_keys.cache_clear()
    issuer = "https://identity.example/application/o/test/"
    monkeypatch.setattr(settings, "AUTH_MODE", "oidc")
    monkeypatch.setattr(settings, "OIDC_ISSUER", issuer)
    monkeypatch.setattr(settings, "OIDC_CLIENT_ID", "self-checkout-test")
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    public = jwt.algorithms.RSAAlgorithm.to_jwk(key.public_key(), as_dict=True)
    public["kid"] = "test-key"
    subject = str(uuid.uuid4())
    email = f"{subject}@example.com"
    info = {
        "sub": subject,
        "email": email,
        "name": "OIDC user",
        "groups": [settings.OIDC_ADMIN_GROUP],
    }
    monkeypatch.setattr(
        oidc,
        "discovery",
        lambda _: {
            "jwks_uri": issuer + "keys",
            "userinfo_endpoint": issuer + "userinfo",
        },
    )
    monkeypatch.setattr(
        oidc,
        "provider_json",
        lambda url, token=None: {"keys": [public]} if url.endswith("keys") else info,
    )
    payload = {
        "iss": issuer,
        "aud": settings.OIDC_CLIENT_ID,
        "sub": subject,
        "iat": datetime.now(UTC),
        "exp": datetime.now(UTC) + timedelta(minutes=5),
    }

    def headers(**updates: object) -> dict[str, str]:
        return {
            "Authorization": "Bearer "
            + jwt.encode(
                {**payload, **updates},
                key,
                algorithm="RS256",
                headers={"kid": "test-key"},
            )
        }

    assert (
        client.get("/api/v1/users/me", headers=headers()).json()["is_superuser"] is True
    )
    info["groups"] = [settings.OIDC_USER_GROUP]
    assert (
        client.get("/api/v1/users/me", headers=headers()).json()["is_superuser"]
        is False
    )
    assert client.get("/api/v1/users/", headers=headers()).status_code == 403
    info["groups"] = []
    assert client.get("/api/v1/users/me", headers=headers()).status_code == 403
    info["groups"] = [settings.OIDC_USER_GROUP]
    assert (
        client.get("/api/v1/users/me", headers=headers(aud="other-app")).status_code
        == 401
    )
    assert (
        client.get(
            "/api/v1/users/me",
            headers=headers(exp=datetime.now(UTC) - timedelta(seconds=5)),
        ).status_code
        == 401
    )
    assert (
        client.get(
            "/api/v1/users/me", headers=headers(iss="https://attacker.example")
        ).status_code
        == 401
    )
    info["email"] = ""
    missing_email = client.get("/api/v1/users/me", headers=headers())
    assert missing_email.status_code == 403
    assert missing_email.json()["detail"]["code"] == "oidc_email_required"
    info["email"] = email
    row = db.exec(select(User).where(User.email == email)).one()
    assert row.hashed_password == "!"
    # Switching back to local mode must deny an OIDC-only account, not crash
    # while attempting to parse its deliberately unusable password hash.
    monkeypatch.setattr(settings, "AUTH_MODE", "local")
    assert (
        client.post(
            "/api/v1/login/access-token",
            data={"username": email, "password": "not-a-local-password"},
        ).status_code
        == 400
    )
    monkeypatch.setattr(settings, "AUTH_MODE", "oidc")
    row.is_active = False
    db.add(row)
    db.commit()
    assert client.get("/api/v1/users/me", headers=headers()).status_code == 403
    row.is_active = True
    row.oidc_subject = "different-identity"
    db.add(row)
    db.commit()
    assert client.get("/api/v1/users/me", headers=headers()).status_code == 409

    def deny_userinfo(_url: str, token: str | None = None) -> dict:
        if token:
            raise HTTPException(401, "Not an access token")
        return {"keys": [public]}

    monkeypatch.setattr(oidc, "provider_json", deny_userinfo)
    assert client.get("/api/v1/users/me", headers=headers()).status_code == 401
