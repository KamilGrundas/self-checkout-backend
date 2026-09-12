from collections.abc import Generator
from typing import Annotated

import jwt
from fastapi import Depends, HTTPException, Request, status
from fastapi.security import APIKeyHeader, OAuth2PasswordBearer
from jwt.exceptions import InvalidTokenError
from pydantic import ValidationError
from sqlmodel import Session

from app.core import security
from app.core.api_keys import (
    authenticate_api_key,
    authenticate_checkout_counter_api_key,
)
from app.core.config import settings
from app.core.db import engine
from app.core.oidc import oidc_user
from app.models import CheckoutCounter, TokenPayload, User

reusable_oauth2 = OAuth2PasswordBearer(
    tokenUrl=f"{settings.API_V1_STR}/login/access-token", auto_error=False
)


def get_db() -> Generator[Session]:
    with Session(engine) as session:
        yield session


SessionDep = Annotated[Session, Depends(get_db)]
TokenDep = Annotated[str | None, Depends(reusable_oauth2)]


def get_current_user(
    session: SessionDep,
    token: TokenDep,
    request: Request = None,  # type: ignore[assignment]
) -> User:
    raw_key = request.headers.get("X-API-Key") if request else None
    if raw_key and token:
        raise HTTPException(400, "Use one authentication method per request")
    credential = raw_key or token
    if credential and (raw_key or credential.startswith("sck_")):
        key = authenticate_api_key(session, credential)
        if not key.role or not key.owner_id:
            raise HTTPException(
                403, "This scoped key cannot access user or admin resources"
            )
        owner = session.get(User, key.owner_id)
        assert owner is not None
        return (
            owner
            if key.role == "admin"
            else owner.model_copy(update={"is_superuser": False})
        )
    if not token:
        raise HTTPException(401, "Authentication required")
    if settings.AUTH_MODE == "oidc":
        return oidc_user(session, token)
    try:
        payload = jwt.decode(
            token,
            settings.SECRET_KEY,
            algorithms=[security.ALGORITHM],
            options={"require": ["exp", "sub"]},
        )
        token_data = TokenPayload(**payload)
    except InvalidTokenError, ValidationError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials",
        )
    user = session.get(User, token_data.sub)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    if not user.is_active:
        raise HTTPException(status_code=400, detail="Inactive user")
    return user


CurrentUser = Annotated[User, Depends(get_current_user)]


def get_current_active_superuser(current_user: CurrentUser) -> User:
    if not current_user.is_superuser:
        raise HTTPException(
            status_code=403, detail="The user doesn't have enough privileges"
        )
    return current_user


optional_bearer = OAuth2PasswordBearer(
    tokenUrl=f"{settings.API_V1_STR}/login/access-token", auto_error=False
)
api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)
OptionalBearer = Annotated[str | None, Depends(optional_bearer)]
OptionalApiKey = Annotated[str | None, Depends(api_key_header)]


def require_checkout_counter(
    request: Request, session: SessionDep, _bearer: OptionalBearer, _key: OptionalApiKey
) -> CheckoutCounter:
    raw_key = request.headers.get("X-API-Key")
    authorization = request.headers.get("Authorization", "")
    if raw_key and authorization:
        raise HTTPException(400, "Use one authentication method per request")
    if not raw_key:
        raise HTTPException(401, "Checkout counter API key required")
    _, counter = authenticate_checkout_counter_api_key(
        session, raw_key, "checkout:session"
    )
    return counter


CheckoutCounterDep = Annotated[CheckoutCounter, Depends(require_checkout_counter)]


def require_catalog_read(
    request: Request, session: SessionDep, _bearer: OptionalBearer, _key: OptionalApiKey
) -> None:
    require_catalog_access(request, session, "catalog:read")


def require_catalog_write(
    request: Request, session: SessionDep, _bearer: OptionalBearer, _key: OptionalApiKey
) -> None:
    require_catalog_access(request, session, "catalog:write")


def require_catalog_access(request: Request, session: Session, scope: str) -> None:
    raw_key = request.headers.get("X-API-Key")
    authorization = request.headers.get("Authorization", "")
    if raw_key and authorization:
        raise HTTPException(400, "Use one authentication method per request")
    if raw_key:
        authenticate_api_key(session, raw_key, scope)
        return
    scheme, _, token = authorization.partition(" ")
    if scheme.lower() != "bearer" or not token:
        raise HTTPException(
            401, "Authentication required", headers={"WWW-Authenticate": "Bearer"}
        )
    user = get_current_user(session, token)
    if scope == "catalog:write" and not user.is_superuser:
        raise HTTPException(403, "The user doesn't have enough privileges")
