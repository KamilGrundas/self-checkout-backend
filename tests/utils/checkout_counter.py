from sqlmodel import Session

from app import crud
from app.models import CheckoutCounter, CheckoutCounterCreate
from tests.utils.utils import random_lower_string


def create_random_checkout_counter(db: Session) -> CheckoutCounter:
    counter, _ = crud.create_checkout_counter(
        session=db,
        counter_in=CheckoutCounterCreate(name=f"counter-{random_lower_string()}"),
    )
    return counter


def create_random_checkout_counter_with_key(db: Session) -> tuple[CheckoutCounter, str]:
    return crud.create_checkout_counter(
        session=db,
        counter_in=CheckoutCounterCreate(name=f"counter-{random_lower_string()}"),
    )
