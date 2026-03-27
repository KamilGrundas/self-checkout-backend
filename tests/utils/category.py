from sqlmodel import Session

from app import crud
from app.models import Category, CategoryCreate
from tests.utils.utils import random_lower_string


def create_random_category(db: Session) -> Category:
    category_in = CategoryCreate(name=f"Category {random_lower_string()}")
    return crud.create_category(session=db, category_in=category_in)
