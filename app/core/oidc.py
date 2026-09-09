"""Provider-neutral OIDC access-token validation; never link accounts by email."""

from functools import lru_cache
from time import monotonic
from typing import Any
from urllib.parse import urlsplit

import httpx
import jwt
from fastapi import HTTPException
from pydantic import EmailStr, TypeAdapter, ValidationError
from sqlalchemy.exc import IntegrityError
from sqlmodel import Session, select

from app.core.config import settings
from app.models import User


def provider_json(url: str, token: str | None = None) -> dict[str, Any]:
    expected = urlsplit(settings.OIDC_ISSUER)
    actual = urlsplit(url)
    if (actual.scheme, actual.netloc) != (expected.scheme, expected.netloc):
        raise HTTPException(503, "OIDC endpoint origin is not trusted")
    try:
        with httpx.Client(
            timeout=10, trust_env=False, follow_redirects=False
        ) as client:
            response = client.get(
                url, headers={"Authorization": f"Bearer {token}"} if token else {}
            )
            if response.status_code in (401, 403):
                raise HTTPException(401, "Invalid OIDC access token")
            response.raise_for_status()
            data = response.json()
            if not isinstance(data, dict):
                raise ValueError("Invalid provider response")
            return data
    except httpx.HTTPError, ValueError:
        raise HTTPException(503, "Identity provider unavailable")


@lru_cache(maxsize=4)
def discovery(issuer: str) -> dict[str, Any]:
    data = provider_json(issuer.rstrip("/") + "/.well-known/openid-configuration")
    if data.get("issuer") != issuer:
        raise HTTPException(503, "OIDC issuer mismatch")
    return data


@lru_cache(maxsize=8)
def cached_keys(url: str, window: int) -> list[dict[str, Any]]:
    del window  # A short TTL also permits key rotation without a process restart.
    return list(provider_json(url)["keys"])


def oidc_user(session: Session, token: str) -> User:
    metadata = discovery(settings.OIDC_ISSUER)
    try:
        header = jwt.get_unverified_header(token)
        if header.get("alg") != "RS256":
            raise ValueError("Unsupported signing algorithm")
        keys = cached_keys(metadata["jwks_uri"], int(monotonic() // 30))
        key = next(k for k in keys if k.get("kid") == header.get("kid"))
        claims = jwt.decode(
            token,
            jwt.PyJWK.from_dict(key).key,
            algorithms=["RS256"],
            issuer=settings.OIDC_ISSUER,
            audience=settings.OIDC_CLIENT_ID,
            options={"require": ["exp", "iat", "iss", "aud", "sub"]},
        )
        # UserInfo accepts access tokens, not ID tokens, and checks current access.
        info = provider_json(metadata["userinfo_endpoint"], token)
        if info.get("sub") != claims["sub"]:
            raise ValueError("Subject mismatch")
        groups = info.get("groups", [])
        if not isinstance(groups, list) or not all(isinstance(g, str) for g in groups):
            raise ValueError("Invalid groups")
        admin = settings.OIDC_ADMIN_GROUP in groups
        if not admin and settings.OIDC_USER_GROUP not in groups:
            raise HTTPException(403, "No self-checkout access group")
        try:
            email = str(TypeAdapter(EmailStr).validate_python(info.get("email")))
        except ValidationError:
            raise HTTPException(403, {"code": "oidc_email_required"})
        subject = claims["sub"]
        if not isinstance(subject, str) or not subject or len(subject) > 255:
            raise ValueError("Invalid subject")
    except jwt.InvalidTokenError, ValueError, KeyError, StopIteration, ValidationError:
        raise HTTPException(401, "Invalid OIDC access token")
    user = session.exec(
        select(User).where(
            User.oidc_issuer == settings.OIDC_ISSUER,
            User.oidc_subject == subject,
        )
    ).first()
    if user and not user.is_active:
        raise HTTPException(403, "Inactive user")
    if not user:
        if session.exec(select(User).where(User.email == email)).first():
            raise HTTPException(
                409,
                "Email already exists; an administrator must explicitly link the OIDC identity",
            )
        user = User(
            email=email,
            hashed_password="!",
            oidc_issuer=settings.OIDC_ISSUER,
            oidc_subject=subject,
        )
    user.is_superuser = admin
    user.full_name = str(info.get("name") or email)[:255]
    session.add(user)
    try:
        session.commit()
        session.refresh(user)
    except IntegrityError:
        session.rollback()
        raise HTTPException(
            409, "Conflicting identity; retry or contact an administrator"
        )
    return user
