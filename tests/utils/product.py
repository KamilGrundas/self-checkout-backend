from decimal import Decimal

from sqlmodel import Session

from app import crud
from app.models import Product, ProductCreate, ProductUnit
from tests.utils.utils import random_lower_string


def create_random_product(db: Session) -> Product:
    product_in = ProductCreate(
        name=random_lower_string(),
        price=Decimal("12.34"),
        unit=ProductUnit.pcs,
    )
    return crud.create_product(session=db, product_in=product_in)
