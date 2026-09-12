import hashlib
import secrets
import uuid
from datetime import UTC, datetime, timedelta
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field, SecretStr
from sqlmodel import col, select

from app.api.deps import SessionDep, get_current_active_superuser
from app.core.autolabel_credentials import encrypt_api_key
from app.core.config import settings
from app.models import ApiKey, AutolabelSettings, Message, User

router = APIRouter(
    prefix="/api-keys",
    tags=["api-keys"],
    dependencies=[Depends(get_current_active_superuser)],
)


class ApiKeyCreate(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    role: Literal["user", "admin"] = "user"
    expires_in_days: int | None = Field(default=None, ge=1, le=365)


class ApiKeyPublic(BaseModel):
    id: uuid.UUID
    name: str
    prefix: str
    scopes: list[str]
    expires_at: datetime | None
    role: str | None
    created_at: datetime
    revoked: bool


class ApiKeyCreated(ApiKeyPublic):
    key: str


@router.post("/", response_model=ApiKeyCreated, status_code=201)
def create_api_key(
    body: ApiKeyCreate,
    session: SessionDep,
    current_user: Annotated[User, Depends(get_current_active_superuser)],
) -> ApiKeyCreated:
    if not settings.API_KEYS_ENABLED:
        raise HTTPException(403, "API keys are disabled")
    raw = "sck_" + secrets.token_urlsafe(32)
    key = ApiKey(
        name=body.name,
        scopes=[],
        role=body.role,
        owner_id=current_user.id,
        prefix=raw[:12],
        key_hash=hashlib.sha256(raw.encode()).hexdigest(),
        expires_at=(datetime.now(UTC) + timedelta(days=body.expires_in_days))
        if body.expires_in_days is not None
        else None,
    )
    session.add(key)
    session.commit()
    session.refresh(key)
    return ApiKeyCreated(
        **ApiKeyPublic.model_validate(key, from_attributes=True).model_dump(), key=raw
    )


@router.get("/", response_model=list[ApiKeyPublic])
def list_api_keys(session: SessionDep) -> list[ApiKey]:
    return list(
        session.exec(
            select(ApiKey)
            .where(ApiKey.purpose == "generic")
            .order_by(col(ApiKey.created_at))
        ).all()
    )


@router.delete("/{key_id}", response_model=Message)
def revoke_api_key(key_id: uuid.UUID, session: SessionDep) -> Message:
    key = session.get(ApiKey, key_id)
    if not key or key.purpose != "generic":
        raise HTTPException(404, "API key not found")
    key.revoked = True
    session.add(key)
    session.commit()
    return Message(message="API key revoked")


class VisionInferenceKeyPublic(BaseModel):
    name: str = "Vision inference provider"
    endpoint_url: str | None = None
    configured: bool = False


class VisionInferenceKeyUpdate(BaseModel):
    endpoint_url: str
    api_key: SecretStr | None = None
    clear_api_key: bool = False


@router.get("/integrations/vision-inference", response_model=VisionInferenceKeyPublic)
def read_vision_inference_key(session: SessionDep) -> VisionInferenceKeyPublic:
    stored = session.get(AutolabelSettings, 1)
    return VisionInferenceKeyPublic(
        endpoint_url=stored.endpoint_url if stored else None,
        configured=bool(stored and stored.api_key_encrypted),
    )


@router.put("/integrations/vision-inference", response_model=VisionInferenceKeyPublic)
def update_vision_inference_key(
    body: VisionInferenceKeyUpdate, session: SessionDep
) -> VisionInferenceKeyPublic:
    stored = session.get(AutolabelSettings, 1)
    if (
        not stored
        or not stored.endpoint_url
        or body.endpoint_url != stored.endpoint_url
    ):
        raise HTTPException(
            409, "Save the autolabel endpoint first and refresh API Keys"
        )
    raw = body.api_key.get_secret_value().strip() if body.api_key else ""
    if raw and (len(raw) > 4096 or any(c.isspace() for c in raw)):
        raise HTTPException(422, "Invalid API token")
    if raw and body.clear_api_key:
        raise HTTPException(422, "Choose replacing or removing the API token")
    if raw and not stored.endpoint_url.startswith("https://"):
        raise HTTPException(422, "An API token requires HTTPS")
    if body.clear_api_key:
        stored.api_key_encrypted = None
    elif raw:
        stored.api_key_encrypted = encrypt_api_key(raw, stored.endpoint_url)
    session.add(stored)
    session.commit()
    return read_vision_inference_key(session)
