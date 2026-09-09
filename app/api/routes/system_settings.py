import httpx
from fastapi import APIRouter, Depends, HTTPException

from app.api.deps import SessionDep, get_current_active_superuser
from app.core.autolabel_models import AvailableModels, discover_models
from app.models import (
    AutolabelSettings,
    AutolabelSettingsPublic,
    AutolabelSettingsRuntime,
    AutolabelSettingsUpdate,
    get_datetime_utc,
)

router = APIRouter(
    prefix="/system-settings",
    tags=["system-settings"],
    dependencies=[Depends(get_current_active_superuser)],
)


def _public(settings: AutolabelSettings | None) -> AutolabelSettingsPublic:
    if settings is None:
        return AutolabelSettingsPublic(configured=False)
    return AutolabelSettingsPublic(
        endpoint_url=settings.endpoint_url,
        model_name=settings.model_name,
        api_key_configured=bool(settings.api_key_encrypted),
        max_tokens=settings.max_tokens,
        connect_timeout_seconds=settings.connect_timeout_seconds,
        read_timeout_seconds=settings.read_timeout_seconds,
        configured=bool(settings.endpoint_url and settings.model_name),
        updated_at=settings.updated_at,
    )


@router.get("/autolabel", response_model=AutolabelSettingsPublic)
def read_autolabel_settings(session: SessionDep) -> AutolabelSettingsPublic:
    return _public(session.get(AutolabelSettings, 1))


@router.put("/autolabel", response_model=AutolabelSettingsPublic)
def update_autolabel_settings(
    session: SessionDep,
    body: AutolabelSettingsUpdate,
) -> AutolabelSettingsPublic:
    stored = session.get(AutolabelSettings, 1)
    if stored is None:
        stored = AutolabelSettings()
    if stored.endpoint_url != body.endpoint_url:
        stored.api_key_encrypted = None
    stored.sqlmodel_update(body.model_dump())
    stored.updated_at = get_datetime_utc()
    session.add(stored)
    session.commit()
    session.refresh(stored)
    return _public(stored)


@router.get("/autolabel/runtime", response_model=AutolabelSettingsRuntime)
def read_autolabel_runtime(session: SessionDep) -> AutolabelSettingsRuntime:
    stored = session.get(AutolabelSettings, 1)
    return AutolabelSettingsRuntime(
        **_public(stored).model_dump(),
        api_key_encrypted=stored.api_key_encrypted if stored else None,
    )


@router.get("/autolabel/models", response_model=AvailableModels)
def list_autolabel_models(session: SessionDep) -> AvailableModels:
    stored = session.get(AutolabelSettings, 1)
    if not stored or not stored.endpoint_url:
        raise HTTPException(409, "Save the autolabel endpoint first")
    try:
        return discover_models(stored)
    except httpx.HTTPStatusError as exc:
        if exc.response.status_code in {401, 403}:
            raise HTTPException(
                502, "Vision inference provider rejected the API token; check API Keys"
            ) from exc
        raise HTTPException(
            502, "Vision inference provider model discovery failed"
        ) from exc
    except httpx.HTTPError, ValueError:
        raise HTTPException(502, "Could not fetch models; check endpoint and API Keys")
