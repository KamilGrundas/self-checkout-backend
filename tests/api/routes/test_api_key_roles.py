import hashlib
import uuid
from datetime import UTC, datetime, timedelta

import pytest

from app.models import ApiKey, User

URL = "/api/v1/api-keys/"


def mint(client, headers, role="user", **extra):
    r = client.post(
        URL, headers=headers, json={"name": "role-test", "role": role, **extra}
    )
    assert r.status_code == 201
    return r.json()


@pytest.mark.parametrize("header", ["X-API-Key", "Authorization"])
def test_role_keys_enforce_permissions(client, superuser_token_headers, header):
    for role in ["user", "admin"]:
        key = mint(client, superuser_token_headers, role)
        headers = {
            header: ("Bearer " if header == "Authorization" else "") + key["key"]
        }
        assert key["expires_at"] is None
        assert client.get("/api/v1/products/", headers=headers).status_code == 200
        me = client.get("/api/v1/users/me", headers=headers)
        assert me.status_code == 200
        assert me.json()["is_superuser"] is (role == "admin")
        for path in [
            "users/",
            "api-keys/",
            "api-keys/integrations/vision-inference",
            "system-settings/autolabel",
            "checkout-counters/",
        ]:
            assert client.get("/api/v1/" + path, headers=headers).status_code == (
                200 if role == "admin" else 403
            )
        assert client.post(
            "/api/v1/login/api-key/check?scope=ml:invoke",
            headers={"X-API-Key": key["key"]},
        ).status_code == (200 if role == "admin" else 403)
        assert key["key"] not in client.get(URL, headers=superuser_token_headers).text


def test_expiration_validation_and_role_validation(client, superuser_token_headers):
    key = mint(client, superuser_token_headers, expires_in_days=2)
    delta = datetime.fromisoformat(key["expires_at"]) - datetime.now(UTC)
    assert timedelta(days=1, hours=23) < delta <= timedelta(days=2)
    for body in [{"expires_in_days": 0}, {"expires_in_days": 366}, {"role": "root"}]:
        assert (
            client.post(
                URL, headers=superuser_token_headers, json={"name": "invalid", **body}
            ).status_code
            == 422
        )
    assert (
        mint(client, superuser_token_headers, expires_in_days=None)["expires_at"]
        is None
    )


def test_owner_changes_disable_role_keys(client, superuser_token_headers, db):
    key = mint(client, superuser_token_headers, "admin")
    row = db.get(ApiKey, uuid.UUID(key["id"]))
    owner = db.get(User, row.owner_id)
    headers = {"X-API-Key": key["key"]}
    try:
        owner.is_superuser = False
        db.add(owner)
        db.commit()
        assert client.get("/api/v1/users/", headers=headers).status_code == 403
        owner.is_superuser = True
        owner.is_active = False
        db.add(owner)
        db.commit()
        assert client.get("/api/v1/users/", headers=headers).status_code == 401
    finally:
        owner.is_superuser = True
        owner.is_active = True
        db.add(owner)
        db.commit()
    row.owner_id = None
    db.add(row)
    db.commit()
    assert client.get("/api/v1/users/", headers=headers).status_code == 401


def test_legacy_scope_key_is_not_promoted(client, db):
    raw = "sck_legacy-test-only"
    row = ApiKey(
        name="legacy",
        key_hash=hashlib.sha256(raw.encode()).hexdigest(),
        prefix="sck_legacy",
        scopes=["catalog:read"],
        expires_at=datetime.now(UTC) + timedelta(days=1),
    )
    db.add(row)
    db.commit()
    headers = {"X-API-Key": raw}
    assert client.get("/api/v1/products/", headers=headers).status_code == 200
    assert client.get("/api/v1/users/", headers=headers).status_code == 403
    assert client.post("/api/v1/products/", headers=headers, json={}).status_code == 403


def test_mixed_credentials_are_rejected(client, superuser_token_headers):
    key = mint(client, superuser_token_headers)
    headers = {**superuser_token_headers, "X-API-Key": key["key"]}
    assert client.get("/api/v1/users/me", headers=headers).status_code == 400
    assert client.get("/api/v1/products/", headers=headers).status_code == 400
