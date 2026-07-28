from fastapi import APIRouter, Depends

from app.api.deps import SessionDep, get_current_active_superuser
from app.models import (
    AutolabelSettings,
    AutolabelSettingsPublic,
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
        max_tokens=settings.max_tokens,
        connect_timeout_seconds=settings.connect_timeout_seconds,
        read_timeout_seconds=settings.read_timeout_seconds,
        configured=bool(settings.endpoint_url),
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
    stored.sqlmodel_update(body.model_dump())
    stored.updated_at = get_datetime_utc()
    session.add(stored)
    session.commit()
    session.refresh(stored)
    return _public(stored)
