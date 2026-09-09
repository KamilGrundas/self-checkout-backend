import hashlib
from datetime import UTC, datetime

from fastapi import HTTPException
from sqlmodel import Session, select

from app.core.config import settings
from app.models import ApiKey, User

API_KEY_SCOPES = {"catalog:read", "catalog:write", "ml:invoke"}


def authenticate_api_key(
    session: Session, raw: str, scope: str | None = None
) -> ApiKey:
    if not settings.API_KEYS_ENABLED or not raw.startswith("sck_") or len(raw) > 256:
        raise HTTPException(401, "Invalid API key")
    digest = hashlib.sha256(raw.encode()).hexdigest()
    key = session.exec(select(ApiKey).where(ApiKey.key_hash == digest)).first()
    if (
        not key
        or key.revoked
        or (key.expires_at is not None and key.expires_at <= datetime.now(UTC))
    ):
        raise HTTPException(401, "Invalid or expired API key")
    if key.role is not None:
        owner = session.get(User, key.owner_id) if key.owner_id else None
        if not owner or not owner.is_active or key.role not in {"user", "admin"}:
            raise HTTPException(401, "API key owner is unavailable")
        if key.role == "admin" and not owner.is_superuser:
            raise HTTPException(403, "API key owner no longer has admin permissions")
        granted = API_KEY_SCOPES if key.role == "admin" else {"catalog:read"}
    else:
        granted = set(key.scopes)
    if scope is not None and scope not in granted:
        raise HTTPException(403, "API key does not grant the required scope")
    return key
