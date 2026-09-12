from fastapi import APIRouter, Depends

from app.api.deps import SessionDep, get_current_active_superuser
from app.models import (
    AutolabelSettings,
    AutolabelSettingsPublic,
    AutolabelSettingsRuntime,
    VisionInferenceIntegration,
)

router = APIRouter(
    prefix="/system-settings",
    tags=["system-settings"],
    dependencies=[Depends(get_current_active_superuser)],
)


def _public(
    settings: AutolabelSettings | None, session: SessionDep
) -> AutolabelSettingsPublic:
    integration = settings and session.get(
        VisionInferenceIntegration, settings.active_integration_id
    )
    if integration is None:
        return AutolabelSettingsPublic(configured=False)
    return AutolabelSettingsPublic(
        endpoint_url=integration.endpoint_url,
        model_name=integration.model_name or "",
        api_key_configured=bool(integration.api_key_encrypted),
        max_tokens=settings.max_tokens if settings else 512,
        connect_timeout_seconds=settings.connect_timeout_seconds if settings else 5,
        read_timeout_seconds=integration.read_timeout_seconds,
        configured=bool(integration.model_name and integration.api_key_encrypted),
        updated_at=integration.updated_at,
    )


@router.get("/autolabel", response_model=AutolabelSettingsPublic)
def read_autolabel_settings(session: SessionDep) -> AutolabelSettingsPublic:
    return _public(session.get(AutolabelSettings, 1), session)


@router.get("/autolabel/runtime", response_model=AutolabelSettingsRuntime)
def read_autolabel_runtime(session: SessionDep) -> AutolabelSettingsRuntime:
    stored = session.get(AutolabelSettings, 1)
    integration = (
        session.get(VisionInferenceIntegration, stored.active_integration_id)
        if stored and stored.active_integration_id
        else None
    )
    return AutolabelSettingsRuntime(
        **_public(stored, session).model_dump(),
        api_key_encrypted=integration.api_key_encrypted if integration else None,
    )
