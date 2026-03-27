from sqlmodel import Session

from app import crud
from app.models import CheckoutCounter, CheckoutCounterCreate
from tests.utils.utils import random_lower_string


def create_random_checkout_counter(db: Session) -> CheckoutCounter:
    counter_in = CheckoutCounterCreate(
        name=f"counter-{random_lower_string()}",
        password="secret-password",
    )
    return crud.create_checkout_counter(session=db, counter_in=counter_in)
