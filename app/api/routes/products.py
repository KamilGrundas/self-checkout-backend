import uuid
from typing import Any

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from sqlmodel import col, func, select

from app import crud
from app.api.deps import SessionDep, get_current_active_superuser
from app.core import object_storage
from app.models import (
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
        .order_by(col(Product.created_at).desc())
        .offset(skip)
        .limit(limit)
    )
    products = session.exec(statement).all()
    return ProductsPublic(data=products, count=count)


@router.get("/{id}", response_model=ProductPublic)
def read_product(session: SessionDep, id: uuid.UUID) -> Any:
    """
    Get product by ID.
    """
    product = session.get(Product, id)
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")
    return product


@router.post(
    "/",
    response_model=ProductPublic,
    dependencies=[Depends(get_current_active_superuser)],
)
def create_product(*, session: SessionDep, product_in: ProductCreate) -> Any:
    """
    Create new product.
    """
    return crud.create_product(session=session, product_in=product_in)


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
    product.sqlmodel_update(update_dict)
    session.add(product)
    session.commit()
    session.refresh(product)
    return product


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
    session.refresh(product)
    return product


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
