import uuid
from typing import Any

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from sqlalchemy.orm import selectinload
from sqlmodel import col, func, select

from app import crud
from app.api.deps import SessionDep, get_current_active_superuser
from app.core import object_storage
from app.models import (
    Category,
    Message,
    Product,
    ProductCreate,
    ProductPublic,
    ProductsPublic,
    ProductUpdate,
)

router = APIRouter(prefix="/products", tags=["products"])


@router.get("/", response_model=ProductsPublic)
def read_products(session: SessionDep, skip: int = 0, limit: int = 100) -> Any:
    """
    Retrieve products.
    """
    count_statement = select(func.count()).select_from(Product)
    count = session.exec(count_statement).one()
    statement = (
        select(Product)
        .options(selectinload(Product.category))
        .order_by(col(Product.created_at).desc())
        .offset(skip)
        .limit(limit)
    )
    products = session.exec(statement).all()
    return ProductsPublic(
        data=[ProductPublic.from_product(product) for product in products],
        count=count,
    )


@router.get("/{id}", response_model=ProductPublic)
def read_product(session: SessionDep, id: uuid.UUID) -> Any:
    """
    Get product by ID.
    """
    statement = select(Product).options(selectinload(Product.category)).where(Product.id == id)
    product = session.exec(statement).first()
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")
    return ProductPublic.from_product(product)


@router.post(
    "/",
    response_model=ProductPublic,
    dependencies=[Depends(get_current_active_superuser)],
)
def create_product(*, session: SessionDep, product_in: ProductCreate) -> Any:
    """
    Create new product.
    """
    if product_in.category_id and not session.get(Category, product_in.category_id):
        raise HTTPException(status_code=404, detail="Category not found")
    product = crud.create_product(session=session, product_in=product_in)
    statement = select(Product).options(selectinload(Product.category)).where(Product.id == product.id)
    product_with_category = session.exec(statement).one()
    return ProductPublic.from_product(product_with_category)


@router.put(
    "/{id}",
    response_model=ProductPublic,
    dependencies=[Depends(get_current_active_superuser)],
)
def update_product(
    *, session: SessionDep, id: uuid.UUID, product_in: ProductUpdate
) -> Any:
    """
    Update a product.
    """
    product = session.get(Product, id)
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")
    update_dict = product_in.model_dump(exclude_unset=True)
    if "category_id" in update_dict and update_dict["category_id"] is None:
        update_dict["category_id"] = crud.ensure_default_category(session).id
    if "category_id" in update_dict and update_dict["category_id"] is not None:
        if not session.get(Category, update_dict["category_id"]):
            raise HTTPException(status_code=404, detail="Category not found")
    product.sqlmodel_update(update_dict)
    session.add(product)
    session.commit()
    statement = select(Product).options(selectinload(Product.category)).where(Product.id == product.id)
    product_with_category = session.exec(statement).one()
    return ProductPublic.from_product(product_with_category)


@router.post(
    "/{id}/image",
    response_model=ProductPublic,
    dependencies=[Depends(get_current_active_superuser)],
)
async def upload_product_image(
    *, session: SessionDep, id: uuid.UUID, file: UploadFile = File(...)
) -> Any:
    """
    Upload a product image.
    """
    product = session.get(Product, id)
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")
    if not file.content_type or not file.content_type.startswith("image/"):
        raise HTTPException(status_code=400, detail="Invalid image file")
    data = await file.read()
    if not data:
        raise HTTPException(status_code=400, detail="Empty image file")
    product.image_url = object_storage.store_product_image(
        product_id=product.id,
        filename=file.filename,
        content_type=file.content_type,
        data=data,
    )
    session.add(product)
    session.commit()
    statement = select(Product).options(selectinload(Product.category)).where(Product.id == product.id)
    product_with_category = session.exec(statement).one()
    return ProductPublic.from_product(product_with_category)


@router.delete("/{id}", dependencies=[Depends(get_current_active_superuser)])
def delete_product(session: SessionDep, id: uuid.UUID) -> Message:
    """
    Delete a product.
    """
    product = session.get(Product, id)
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")
    session.delete(product)
    session.commit()
    return Message(message="Product deleted successfully")
