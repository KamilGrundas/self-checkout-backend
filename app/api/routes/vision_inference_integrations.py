import uuid

import httpx
from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import select

from app.api.deps import SessionDep, get_current_active_superuser
from app.core.autolabel_credentials import encrypt_api_key
from app.core.autolabel_models import AvailableModels, discover_models
from app.models import (
    AutolabelSettings,
    VisionInferenceIntegration,
    VisionInferenceIntegrationCreate,
    VisionInferenceIntegrationPublic,
    VisionInferenceIntegrationUpdate,
    get_datetime_utc,
)

router = APIRouter(
    prefix="/vision-inference-integrations",
    tags=["vision-inference-integrations"],
    dependencies=[Depends(get_current_active_superuser)],
)


def _configured(row: VisionInferenceIntegration) -> bool:
    return bool(row.endpoint_url and row.model_name and row.api_key_encrypted)


def _public(row: VisionInferenceIntegration) -> VisionInferenceIntegrationPublic:
    active_model: str | None = None
    model_loaded = False
    try:
        discovered = discover_models(row.endpoint_url, row.api_key_encrypted)
        active_model = discovered.active_model
        model_loaded = bool(active_model)
    except httpx.HTTPError, ValueError:
        pass
    return VisionInferenceIntegrationPublic(
        id=row.id,
        name=row.name,
        endpoint_url=row.endpoint_url,
        model_name=row.model_name,
        api_key_configured=bool(row.api_key_encrypted),
        configured=_configured(row),
        active=row.active,
        active_model=active_model,
        model_loaded=model_loaded,
    )


def _row_or_404(
    integration_id: uuid.UUID, session: SessionDep
) -> VisionInferenceIntegration:
    row = session.get(VisionInferenceIntegration, integration_id)
    if row is None:
        raise HTTPException(404, "Vision inference integration not found")
    return row


@router.get("/", response_model=list[VisionInferenceIntegrationPublic])
def list_integrations(session: SessionDep) -> list[VisionInferenceIntegrationPublic]:
    rows = session.exec(
        select(VisionInferenceIntegration).order_by(VisionInferenceIntegration.name)
    ).all()
    return [_public(row) for row in rows]


@router.post("/", response_model=VisionInferenceIntegrationPublic, status_code=201)
def create_integration(
    body: VisionInferenceIntegrationCreate, session: SessionDep
) -> VisionInferenceIntegrationPublic:
    raw_key = body.api_key.strip()
    if not raw_key or any(char.isspace() for char in raw_key):
        raise HTTPException(422, "Invalid API token")
    if not body.endpoint_url.startswith("https://"):
        raise HTTPException(422, "An API token requires HTTPS")
    row = VisionInferenceIntegration(
        name=body.name,
        endpoint_url=body.endpoint_url,
        model_name=body.model_name,
        api_key_encrypted=encrypt_api_key(raw_key, body.endpoint_url),
    )
    session.add(row)
    session.commit()
    session.refresh(row)
    return _public(row)


@router.patch("/{integration_id}", response_model=VisionInferenceIntegrationPublic)
def update_integration(
    integration_id: uuid.UUID,
    body: VisionInferenceIntegrationUpdate,
    session: SessionDep,
) -> VisionInferenceIntegrationPublic:
    row = _row_or_404(integration_id, session)
    changes = body.model_dump(exclude_unset=True)
    if "endpoint_url" in changes and changes["endpoint_url"] != row.endpoint_url:
        row.endpoint_url = changes["endpoint_url"]
        row.api_key_encrypted = None
    if "name" in changes:
        row.name = changes["name"]
    if "model_name" in changes:
        row.model_name = changes["model_name"]
    if "read_timeout_seconds" in changes:
        row.read_timeout_seconds = changes["read_timeout_seconds"]
    row.updated_at = get_datetime_utc()
    session.add(row)
    session.commit()
    session.refresh(row)
    return _public(row)


@router.post(
    "/{integration_id}/activate", response_model=VisionInferenceIntegrationPublic
)
def activate_integration(
    integration_id: uuid.UUID, session: SessionDep
) -> VisionInferenceIntegrationPublic:
    row = _row_or_404(integration_id, session)
    if not _configured(row):
        raise HTTPException(409, "Configure an endpoint, API token and model first")
    for candidate in session.exec(select(VisionInferenceIntegration)).all():
        candidate.active = candidate.id == row.id
        session.add(candidate)
    settings = session.get(AutolabelSettings, 1) or AutolabelSettings()
    settings.active_integration_id = row.id
    settings.updated_at = get_datetime_utc()
    session.add(settings)
    session.commit()
    session.refresh(row)
    return _public(row)


@router.get("/{integration_id}/models", response_model=AvailableModels)
def list_models(integration_id: uuid.UUID, session: SessionDep) -> AvailableModels:
    row = _row_or_404(integration_id, session)
    try:
        return discover_models(row.endpoint_url, row.api_key_encrypted)
    except httpx.HTTPStatusError as exc:
        if exc.response.status_code in {401, 403}:
            raise HTTPException(
                502, "Vision inference provider rejected the API token"
            ) from exc
        raise HTTPException(
            502, "Vision inference provider model discovery failed"
        ) from exc
    except (httpx.HTTPError, ValueError) as exc:
        raise HTTPException(
            502, "Could not fetch models; check endpoint and API key"
        ) from exc
