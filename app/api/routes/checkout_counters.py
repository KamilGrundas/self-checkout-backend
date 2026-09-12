import uuid
from typing import Any

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from sqlmodel import col, func, select

from app import crud
from app.api.deps import SessionDep, get_current_active_superuser
from app.core.config import settings
from app.core.ws_manager import manager as ws_manager
from app.models import (
    CheckoutCounter,
    CheckoutCounterApiKeyCreated,
    CheckoutCounterCreate,
    CheckoutCounterCreated,
    CheckoutCounterPublic,
    CheckoutCountersPublic,
    CheckoutCounterUpdate,
    CheckoutSession,
    Message,
)

router = APIRouter(prefix="/checkout-counters", tags=["checkout-counters"])


def _require_api_keys_enabled() -> None:
    if not settings.API_KEYS_ENABLED:
        raise HTTPException(status_code=403, detail="API keys are disabled")


def _validate_camera_selection(
    counter: CheckoutCounter,
    update: CheckoutCounterUpdate,
) -> None:
    available_ids = {
        str(camera.get("device_id"))
        for camera in counter.available_cameras
        if camera.get("device_id")
    }
    for field_name in ("shelf_camera_device_id", "scale_camera_device_id"):
        if field_name not in update.model_fields_set:
            continue
        value = getattr(update, field_name)
        current = getattr(counter, field_name)
        if value is not None and value != current and value not in available_ids:
            raise HTTPException(
                status_code=422,
                detail=f"Selected {field_name} is not available on this checkout counter",
            )


@router.get(
    "/",
    response_model=CheckoutCountersPublic,
    dependencies=[Depends(get_current_active_superuser)],
)
def read_checkout_counters(session: SessionDep) -> Any:
    count_statement = select(func.count()).select_from(CheckoutCounter)
    count = session.exec(count_statement).one()
    statement = select(CheckoutCounter).order_by(col(CheckoutCounter.created_at).desc())
    counters = session.exec(statement).all()
    return CheckoutCountersPublic(data=counters, count=count)


@router.post(
    "/",
    response_model=CheckoutCounterCreated,
    dependencies=[Depends(get_current_active_superuser)],
)
def create_checkout_counter(
    *, session: SessionDep, counter_in: CheckoutCounterCreate
) -> Any:
    _require_api_keys_enabled()
    counter, raw_key = crud.create_checkout_counter(
        session=session, counter_in=counter_in
    )
    return CheckoutCounterCreated(
        **CheckoutCounterPublic.model_validate(
            counter, from_attributes=True
        ).model_dump(),
        api_key=raw_key,
    )


@router.put(
    "/{id}",
    response_model=CheckoutCounterPublic,
    dependencies=[Depends(get_current_active_superuser)],
)
def update_checkout_counter(
    *, session: SessionDep, id: uuid.UUID, counter_in: CheckoutCounterUpdate
) -> Any:
    counter = session.get(CheckoutCounter, id)
    if not counter:
        raise HTTPException(status_code=404, detail="Checkout counter not found")
    _validate_camera_selection(counter, counter_in)
    return crud.update_checkout_counter(
        session=session, db_counter=counter, counter_in=counter_in
    )


@router.post(
    "/{id}/api-key/rotate",
    response_model=CheckoutCounterApiKeyCreated,
    dependencies=[Depends(get_current_active_superuser)],
)
def rotate_checkout_counter_api_key(
    *, session: SessionDep, id: uuid.UUID, background_tasks: BackgroundTasks
) -> CheckoutCounterApiKeyCreated:
    _require_api_keys_enabled()
    counter = session.get(CheckoutCounter, id)
    if not counter:
        raise HTTPException(status_code=404, detail="Checkout counter not found")
    raw_key = crud.rotate_checkout_counter_api_key(session=session, counter=counter)
    sessions = session.exec(
        select(CheckoutSession).where(
            CheckoutSession.counter_id == counter.id,
            col(CheckoutSession.closed).is_(False),
        )
    ).all()
    for checkout_session in sessions:
        background_tasks.add_task(ws_manager.disconnect_clients, checkout_session.id)
    return CheckoutCounterApiKeyCreated(api_key=raw_key)


@router.delete(
    "/{id}",
    response_model=Message,
    dependencies=[Depends(get_current_active_superuser)],
)
def delete_checkout_counter(
    session: SessionDep, id: uuid.UUID, background_tasks: BackgroundTasks
) -> Message:
    counter = session.get(CheckoutCounter, id)
    if not counter:
        raise HTTPException(status_code=404, detail="Checkout counter not found")
    sessions = session.exec(
        select(CheckoutSession).where(CheckoutSession.counter_id == counter.id)
    ).all()
    session.delete(counter)
    session.commit()
    for checkout_session in sessions:
        background_tasks.add_task(ws_manager.disconnect_clients, checkout_session.id)
    return Message(message="Checkout counter deleted successfully")
