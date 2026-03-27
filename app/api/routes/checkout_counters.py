import uuid
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import func, select

from app import crud
from app.api.deps import SessionDep, get_current_active_superuser
from app.models import (
    CheckoutCounter,
    CheckoutCounterCreate,
    CheckoutCounterPublic,
    CheckoutCountersPublic,
    CheckoutCounterUpdate,
    Message,
)

router = APIRouter(prefix="/checkout-counters", tags=["checkout-counters"])


@router.get(
    "/",
    response_model=CheckoutCountersPublic,
    dependencies=[Depends(get_current_active_superuser)],
)
def read_checkout_counters(session: SessionDep) -> Any:
    count_statement = select(func.count()).select_from(CheckoutCounter)
    count = session.exec(count_statement).one()
    statement = select(CheckoutCounter).order_by(CheckoutCounter.created_at.desc())
    counters = session.exec(statement).all()
    return CheckoutCountersPublic(data=counters, count=count)


@router.post(
    "/",
    response_model=CheckoutCounterPublic,
    dependencies=[Depends(get_current_active_superuser)],
)
def create_checkout_counter(
    *, session: SessionDep, counter_in: CheckoutCounterCreate
) -> Any:
    return crud.create_checkout_counter(session=session, counter_in=counter_in)


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
    return crud.update_checkout_counter(
        session=session, db_counter=counter, counter_in=counter_in
    )


@router.delete(
    "/{id}",
    response_model=Message,
    dependencies=[Depends(get_current_active_superuser)],
)
def delete_checkout_counter(session: SessionDep, id: uuid.UUID) -> Message:
    counter = session.get(CheckoutCounter, id)
    if not counter:
        raise HTTPException(status_code=404, detail="Checkout counter not found")
    session.delete(counter)
    session.commit()
    return Message(message="Checkout counter deleted successfully")
