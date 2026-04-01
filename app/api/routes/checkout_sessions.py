import uuid
from typing import Any

from fastapi import APIRouter, HTTPException

from app import crud
from app.api.deps import SessionDep
from app.models import (
    CheckoutSession,
    CheckoutSessionCartUpdate,
    CheckoutSessionConnect,
    CheckoutSessionPayment,
    CheckoutSessionPublic,
)

router = APIRouter(prefix="/checkout-sessions", tags=["checkout-sessions"])


def require_counter(
    *,
    session: SessionDep,
    counter_id: uuid.UUID,
    password: str,
):
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


@router.post("/connect", response_model=CheckoutSessionPublic)
def connect_checkout_session(
    *, session: SessionDep, payload: CheckoutSessionConnect
) -> Any:
    require_counter(
        session=session, counter_id=payload.counter_id, password=payload.password
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
    *, session: SessionDep, id: uuid.UUID, payload: CheckoutSessionCartUpdate
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
    return CheckoutSessionPublic.from_db(checkout_session)


@router.post("/{id}/pay", response_model=CheckoutSessionPublic)
def pay_checkout_session(
    *, session: SessionDep, id: uuid.UUID, payload: CheckoutSessionPayment
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
    return CheckoutSessionPublic.from_db(checkout_session)
