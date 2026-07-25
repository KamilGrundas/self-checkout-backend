import uuid
from datetime import UTC, datetime
from decimal import Decimal
from enum import StrEnum
from typing import Any

from pydantic import EmailStr
from sqlalchemy import JSON, Column, DateTime, Text
from sqlmodel import Field, Relationship, SQLModel

from app.core.object_storage import public_url


def get_datetime_utc() -> datetime:
    return datetime.now(UTC)


# Shared properties
class UserBase(SQLModel):
    email: EmailStr = Field(unique=True, index=True, max_length=255)
    is_active: bool = True
    is_superuser: bool = False
    full_name: str | None = Field(default=None, max_length=255)


# Properties to receive via API on creation
class UserCreate(UserBase):
    password: str = Field(min_length=8, max_length=128)


class UserRegister(SQLModel):
    email: EmailStr = Field(max_length=255)
    password: str = Field(min_length=8, max_length=128)
    full_name: str | None = Field(default=None, max_length=255)


# Properties to receive via API on update, all are optional
class UserUpdate(UserBase):
    email: EmailStr | None = Field(default=None, max_length=255)  # type: ignore
    password: str | None = Field(default=None, min_length=8, max_length=128)


class UserUpdateMe(SQLModel):
    full_name: str | None = Field(default=None, max_length=255)
    email: EmailStr | None = Field(default=None, max_length=255)


class UpdatePassword(SQLModel):
    current_password: str = Field(min_length=8, max_length=128)
    new_password: str = Field(min_length=8, max_length=128)


class LabelStudioSettingsUpdate(SQLModel):
    api_key: str = Field(min_length=1, max_length=2048)


class LabelStudioSettingsPublic(SQLModel):
    api_key_configured: bool


class LabelStudioApiKeySecret(SQLModel):
    api_key: str


# Database model, database table inferred from class name
class User(UserBase, table=True):
    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    hashed_password: str
    created_at: datetime | None = Field(
        default_factory=get_datetime_utc,
        sa_type=DateTime(timezone=True),  # type: ignore
    )
    label_studio_api_key_encrypted: str | None = Field(
        default=None,
        sa_column=Column(Text, nullable=True),
    )
    items: list[Item] = Relationship(back_populates="owner", cascade_delete=True)


# Properties to return via API, id is always required
class UserPublic(UserBase):
    id: uuid.UUID
    created_at: datetime | None = None


class UsersPublic(SQLModel):
    data: list[UserPublic]
    count: int


# Shared properties
class ItemBase(SQLModel):
    title: str = Field(min_length=1, max_length=255)
    description: str | None = Field(default=None, max_length=255)


# Properties to receive on item creation
class ItemCreate(ItemBase):
    pass


# Properties to receive on item update
class ItemUpdate(ItemBase):
    title: str | None = Field(default=None, min_length=1, max_length=255)  # type: ignore


# Database model, database table inferred from class name
class Item(ItemBase, table=True):
    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    created_at: datetime | None = Field(
        default_factory=get_datetime_utc,
        sa_type=DateTime(timezone=True),  # type: ignore
    )
    owner_id: uuid.UUID = Field(
        foreign_key="user.id", nullable=False, ondelete="CASCADE"
    )
    owner: User | None = Relationship(back_populates="items")


# Properties to return via API, id is always required
class ItemPublic(ItemBase):
    id: uuid.UUID
    owner_id: uuid.UUID
    created_at: datetime | None = None


class ItemsPublic(SQLModel):
    data: list[ItemPublic]
    count: int


class ProductUnit(StrEnum):
    kg = "kg"
    pcs = "pcs"


DEFAULT_CATEGORY_ID = uuid.UUID("00000000-0000-0000-0000-000000000001")
DEFAULT_CATEGORY_KEY = "other"
DEFAULT_CATEGORY_NAME = "Other"


class CategoryBase(SQLModel):
    name: str = Field(min_length=1, max_length=255)
    key: str = Field(min_length=1, max_length=255, unique=True, index=True)


class CategoryCreate(SQLModel):
    name: str = Field(min_length=1, max_length=255)


class CategoryUpdate(SQLModel):
    name: str | None = Field(default=None, min_length=1, max_length=255)


class Category(CategoryBase, table=True):
    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    created_at: datetime | None = Field(
        default_factory=get_datetime_utc,
        sa_type=DateTime(timezone=True),  # type: ignore
    )
    products: list[Product] = Relationship(back_populates="category")


class CategoryPublic(CategoryBase):
    id: uuid.UUID
    created_at: datetime | None = None


class CategoriesPublic(SQLModel):
    data: list[CategoryPublic]
    count: int


class ProductBase(SQLModel):
    name: str = Field(min_length=1, max_length=255)
    price: Decimal = Field(max_digits=10, decimal_places=2, ge=0)
    unit: ProductUnit
    image_url: str | None = Field(default=None, max_length=2048)
    thumbnail_url: str | None = Field(default=None, max_length=2048)


class ProductCreate(ProductBase):
    category_id: uuid.UUID | None = None


class ProductUpdate(SQLModel):
    name: str | None = Field(default=None, min_length=1, max_length=255)
    price: Decimal | None = Field(default=None, max_digits=10, decimal_places=2, ge=0)
    unit: ProductUnit | None = None
    image_url: str | None = Field(default=None, max_length=2048)
    category_id: uuid.UUID | None = None


class Product(ProductBase, table=True):
    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    category_id: uuid.UUID = Field(
        foreign_key="category.id", nullable=False, ondelete="RESTRICT"
    )
    created_at: datetime | None = Field(
        default_factory=get_datetime_utc,
        sa_type=DateTime(timezone=True),  # type: ignore
    )
    category: Category | None = Relationship(back_populates="products")


class ProductPublic(ProductBase):
    id: uuid.UUID
    category_id: uuid.UUID
    category_name: str
    category_key: str
    created_at: datetime | None = None

    @classmethod
    def from_product(cls, product: Product) -> ProductPublic:
        if not product.category:
            raise ValueError("Product category must be loaded")
        return cls(
            id=product.id,
            name=product.name,
            price=product.price,
            unit=product.unit,
            image_url=public_url(product.image_url) if product.image_url else None,
            thumbnail_url=public_url(product.thumbnail_url)
            if product.thumbnail_url
            else None,
            category_id=product.category_id,
            category_name=product.category.name,
            category_key=product.category.key,
            created_at=product.created_at,
        )


class ProductsPublic(SQLModel):
    data: list[ProductPublic]
    count: int


class CheckoutMlMode(StrEnum):
    off = "off"
    label = "label"
    on = "on"


class CheckoutCounterSettingsBase(SQLModel):
    ml_mode: CheckoutMlMode = CheckoutMlMode.off
    shelf_camera_device_id: str | None = Field(default=None, max_length=255)
    scale_camera_device_id: str | None = Field(default=None, max_length=255)
    language: str = Field(default="pl", min_length=2, max_length=8)


class CheckoutCounterBase(CheckoutCounterSettingsBase):
    name: str = Field(min_length=1, max_length=255)


class CheckoutCounterCreate(SQLModel):
    name: str = Field(min_length=1, max_length=255)
    password: str = Field(min_length=1, max_length=255)


class CheckoutCounterUpdate(SQLModel):
    name: str | None = Field(default=None, min_length=1, max_length=255)
    password: str | None = Field(default=None, min_length=1, max_length=255)
    ml_mode: CheckoutMlMode | None = None
    shelf_camera_device_id: str | None = Field(default=None, max_length=255)
    scale_camera_device_id: str | None = Field(default=None, max_length=255)
    language: str | None = Field(default=None, min_length=2, max_length=8)


class CheckoutCounterSelfSettingsUpdate(SQLModel):
    counter_id: uuid.UUID
    password: str = Field(min_length=1, max_length=255)
    ml_mode: CheckoutMlMode | None = None
    shelf_camera_device_id: str | None = Field(default=None, max_length=255)
    scale_camera_device_id: str | None = Field(default=None, max_length=255)
    language: str | None = Field(default=None, min_length=2, max_length=8)


class CheckoutCounter(CheckoutCounterBase, table=True):
    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    password_hash: str
    created_at: datetime | None = Field(
        default_factory=get_datetime_utc,
        sa_type=DateTime(timezone=True),  # type: ignore
    )
    sessions: list[CheckoutSession] = Relationship(back_populates="counter")


class CheckoutCounterPublic(CheckoutCounterBase):
    id: uuid.UUID
    created_at: datetime | None = None


class CheckoutCountersPublic(SQLModel):
    data: list[CheckoutCounterPublic]
    count: int


class CheckoutSessionPaymentStatus(StrEnum):
    pending = "pending"
    paid = "paid"


class CheckoutSessionCartItem(SQLModel):
    product_id: uuid.UUID
    name: str
    unit: ProductUnit
    price: float = Field(ge=0)
    quantity: float = Field(gt=0)
    quantity_label: str = Field(min_length=1, max_length=255)
    line_total: float = Field(ge=0)
    image_url: str | None = Field(default=None, max_length=2048)


class CheckoutSessionBase(SQLModel):
    client_id: str = Field(min_length=1, max_length=255)
    closed: bool = False
    payment_status: CheckoutSessionPaymentStatus = CheckoutSessionPaymentStatus.pending


class CheckoutSessionConnect(SQLModel):
    counter_id: uuid.UUID
    password: str = Field(min_length=1, max_length=255)
    client_id: str = Field(min_length=1, max_length=255)


class CheckoutSessionCartUpdate(SQLModel):
    counter_id: uuid.UUID
    password: str = Field(min_length=1, max_length=255)
    client_id: str = Field(min_length=1, max_length=255)
    cart: list[CheckoutSessionCartItem] = Field(default_factory=list)


class CheckoutSessionPayment(SQLModel):
    counter_id: uuid.UUID
    password: str = Field(min_length=1, max_length=255)
    client_id: str = Field(min_length=1, max_length=255)


class CheckoutSession(CheckoutSessionBase, table=True):
    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    counter_id: uuid.UUID = Field(
        foreign_key="checkoutcounter.id", nullable=False, ondelete="CASCADE"
    )
    created_at: datetime | None = Field(
        default_factory=get_datetime_utc,
        sa_type=DateTime(timezone=True),  # type: ignore
    )
    updated_at: datetime | None = Field(
        default_factory=get_datetime_utc,
        sa_type=DateTime(timezone=True),  # type: ignore
    )
    closed_at: datetime | None = Field(
        default=None,
        sa_type=DateTime(timezone=True),  # type: ignore
    )
    cart: list[dict[str, Any]] = Field(
        default_factory=list,
        sa_column=Column(JSON, nullable=False),
    )
    counter: CheckoutCounter | None = Relationship(back_populates="sessions")


class CheckoutSessionPublic(CheckoutSessionBase):
    id: uuid.UUID
    counter_id: uuid.UUID
    cart: list[CheckoutSessionCartItem]
    counter_settings: CheckoutCounterSettingsBase
    created_at: datetime | None = None
    updated_at: datetime | None = None
    closed_at: datetime | None = None

    @classmethod
    def from_db(cls, session: CheckoutSession) -> CheckoutSessionPublic:
        cart_items = [
            CheckoutSessionCartItem.model_validate(item) for item in session.cart or []
        ]
        if session.counter is None:
            raise ValueError("CheckoutSession.counter must be loaded")
        return cls(
            id=session.id,
            counter_id=session.counter_id,
            client_id=session.client_id,
            closed=session.closed,
            payment_status=session.payment_status,
            cart=cart_items,
            counter_settings=CheckoutCounterSettingsBase.model_validate(
                session.counter, from_attributes=True
            ),
            created_at=session.created_at,
            updated_at=session.updated_at,
            closed_at=session.closed_at,
        )


class CheckoutSessionsPublic(SQLModel):
    data: list[CheckoutSessionPublic]
    count: int


# Generic message
class Message(SQLModel):
    message: str


# JSON payload containing access token
class Token(SQLModel):
    access_token: str
    token_type: str = "bearer"


# Contents of JWT token
class TokenPayload(SQLModel):
    sub: str | None = None


class NewPassword(SQLModel):
    token: str
    new_password: str = Field(min_length=8, max_length=128)
