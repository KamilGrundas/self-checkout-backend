import uuid
from typing import Any

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from sqlmodel import col, select

from app import crud
from app.api.deps import SessionDep, get_current_active_superuser
from app.core.ws_manager import manager as ws_manager
from app.models import (
    CheckoutCounter,
    CheckoutSession,
    CheckoutSessionCartUpdate,
    CheckoutSessionConnect,
    CheckoutSessionPayment,
    CheckoutSessionPublic,
    CheckoutSessionsPublic,
)

router = APIRouter(prefix="/checkout-sessions", tags=["checkout-sessions"])


def require_counter(
    *,
    session: SessionDep,
    counter_id: uuid.UUID,
    password: str,
) -> CheckoutCounter:
    counter = crud.authenticate_checkout_counter(
        session=session, counter_id=counter_id, password=password
    )
    if not counter:
        raise HTTPException(
            status_code=403, detail="Invalid checkout counter credentials"
        )
    return counter


def require_session(
    *,
    session: SessionDep,
    session_id: uuid.UUID,
    counter_id: uuid.UUID,
    client_id: str,
) -> CheckoutSession:
    checkout_session = session.get(CheckoutSession, session_id)
    if not checkout_session:
        raise HTTPException(status_code=404, detail="Checkout session not found")
    if (
        checkout_session.counter_id != counter_id
        or checkout_session.client_id != client_id
    ):
        raise HTTPException(status_code=403, detail="Checkout session access denied")
    return checkout_session


@router.get(
    "/active",
    response_model=CheckoutSessionsPublic,
    dependencies=[Depends(get_current_active_superuser)],
)
def list_active_checkout_sessions(session: SessionDep) -> Any:
    statement = (
        select(CheckoutSession)
        .where(col(CheckoutSession.closed).is_(False))
        .order_by(col(CheckoutSession.updated_at).desc())
    )
    sessions = session.exec(statement).all()
    data = [CheckoutSessionPublic.from_db(s) for s in sessions]
    return CheckoutSessionsPublic(data=data, count=len(data))


@router.post("/connect", response_model=CheckoutSessionPublic)
def connect_checkout_session(
    *, session: SessionDep, payload: CheckoutSessionConnect
) -> Any:
    counter = require_counter(
        session=session, counter_id=payload.counter_id, password=payload.password
    )
    if payload.camera_discovery_succeeded:
        crud.update_checkout_counter_cameras(
            session=session,
            db_counter=counter,
            cameras=payload.available_cameras,
        )
    checkout_session = crud.get_open_checkout_session(
        session=session, counter_id=payload.counter_id, client_id=payload.client_id
    )
    if not checkout_session:
        checkout_session = crud.create_checkout_session(
            session=session,
            counter_id=payload.counter_id,
            client_id=payload.client_id,
        )
    return CheckoutSessionPublic.from_db(checkout_session)


@router.put("/{id}/cart", response_model=CheckoutSessionPublic)
def update_checkout_session_cart(
    *,
    session: SessionDep,
    id: uuid.UUID,
    payload: CheckoutSessionCartUpdate,
    background_tasks: BackgroundTasks,
) -> Any:
    require_counter(
        session=session, counter_id=payload.counter_id, password=payload.password
    )
    checkout_session = require_session(
        session=session,
        session_id=id,
        counter_id=payload.counter_id,
        client_id=payload.client_id,
    )
    if checkout_session.closed:
        raise HTTPException(
            status_code=400, detail="Checkout session is already closed"
        )
    checkout_session = crud.update_checkout_session_cart(
        session=session,
        db_session=checkout_session,
        cart=payload.cart,
    )
    public = CheckoutSessionPublic.from_db(checkout_session)
    background_tasks.add_task(_broadcast_session_state, public)
    return public


@router.post("/{id}/pay", response_model=CheckoutSessionPublic)
def pay_checkout_session(
    *,
    session: SessionDep,
    id: uuid.UUID,
    payload: CheckoutSessionPayment,
    background_tasks: BackgroundTasks,
) -> Any:
    require_counter(
        session=session, counter_id=payload.counter_id, password=payload.password
    )
    checkout_session = require_session(
        session=session,
        session_id=id,
        counter_id=payload.counter_id,
        client_id=payload.client_id,
    )
    if checkout_session.closed:
        raise HTTPException(
            status_code=400, detail="Checkout session is already closed"
        )
    checkout_session = crud.close_checkout_session(
        session=session,
        db_session=checkout_session,
    )
    public = CheckoutSessionPublic.from_db(checkout_session)
    background_tasks.add_task(_broadcast_paid_session_and_disconnect, public)
    return public


async def _broadcast_session_state(public: CheckoutSessionPublic) -> None:
    await ws_manager.broadcast(
        public.id,
        {
            "type": "session_state",
            "session": public.model_dump(mode="json"),
            "admin_takeover": ws_manager.is_admin_present(public.id),
        },
    )


async def _broadcast_paid_session_and_disconnect(
    public: CheckoutSessionPublic,
) -> None:
    await ws_manager.broadcast(
        public.id,
        {
            "type": "session_state",
            "session": public.model_dump(mode="json"),
            "admin_takeover": ws_manager.is_admin_present(public.id),
        },
        to_clients=False,
    )
    await ws_manager.disconnect_clients(public.id)
