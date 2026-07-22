import uuid
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import col, func, select

from app import crud
from app.api.deps import SessionDep, get_current_active_superuser
from app.models import (
    DEFAULT_CATEGORY_ID,
    CategoriesPublic,
    Category,
    CategoryCreate,
    CategoryPublic,
    CategoryUpdate,
    Message,
)

router = APIRouter(prefix="/categories", tags=["categories"])


@router.get("/", response_model=CategoriesPublic)
def read_categories(session: SessionDep) -> Any:
    count_statement = select(func.count()).select_from(Category)
    count = session.exec(count_statement).one()
    statement = select(Category).order_by(col(Category.name).asc())
    categories = session.exec(statement).all()
    return CategoriesPublic(data=categories, count=count)


@router.post(
    "/",
    response_model=CategoryPublic,
    dependencies=[Depends(get_current_active_superuser)],
)
def create_category(*, session: SessionDep, category_in: CategoryCreate) -> Any:
    return crud.create_category(session=session, category_in=category_in)


@router.put(
    "/{id}",
    response_model=CategoryPublic,
    dependencies=[Depends(get_current_active_superuser)],
)
def update_category(
    *, session: SessionDep, id: uuid.UUID, category_in: CategoryUpdate
) -> Any:
    category = session.get(Category, id)
    if not category:
        raise HTTPException(status_code=404, detail="Category not found")
    if category.id == DEFAULT_CATEGORY_ID:
        raise HTTPException(
            status_code=400, detail="Default category cannot be renamed"
        )
    return crud.update_category(
        session=session,
        db_category=category,
        category_in=category_in,
    )


@router.delete(
    "/{id}",
    response_model=Message,
    dependencies=[Depends(get_current_active_superuser)],
)
def delete_category(session: SessionDep, id: uuid.UUID) -> Message:
    category = session.get(Category, id)
    if not category:
        raise HTTPException(status_code=404, detail="Category not found")
    if category.id == DEFAULT_CATEGORY_ID:
        raise HTTPException(
            status_code=400, detail="Default category cannot be deleted"
        )
    if category.products:
        raise HTTPException(
            status_code=400,
            detail="Category cannot be deleted while products still use it",
        )
    session.delete(category)
    session.commit()
    return Message(message="Category deleted successfully")
