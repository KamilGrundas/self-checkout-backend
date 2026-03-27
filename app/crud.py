import uuid
from typing import Any

from sqlmodel import Session, select

from app.core.security import get_password_hash, verify_password
from app.models import (
    CheckoutCounter,
    CheckoutCounterCreate,
    CheckoutCounterUpdate,
    CheckoutSession,
    CheckoutSessionCartItem,
    CheckoutSessionPaymentStatus,
    Item,
    ItemCreate,
    Product,
    ProductCreate,
    User,
    UserCreate,
    UserUpdate,
    get_datetime_utc,
)


def create_user(*, session: Session, user_create: UserCreate) -> User:
    db_obj = User.model_validate(
        user_create, update={"hashed_password": get_password_hash(user_create.password)}
    )
    session.add(db_obj)
    session.commit()
    session.refresh(db_obj)
    return db_obj


def update_user(*, session: Session, db_user: User, user_in: UserUpdate) -> Any:
    user_data = user_in.model_dump(exclude_unset=True)
    extra_data = {}
    if "password" in user_data:
        password = user_data["password"]
        hashed_password = get_password_hash(password)
        extra_data["hashed_password"] = hashed_password
    db_user.sqlmodel_update(user_data, update=extra_data)
    session.add(db_user)
    session.commit()
    session.refresh(db_user)
    return db_user


def get_user_by_email(*, session: Session, email: str) -> User | None:
    statement = select(User).where(User.email == email)
    session_user = session.exec(statement).first()
    return session_user


# Dummy hash to use for timing attack prevention when user is not found
# This is an Argon2 hash of a random password, used to ensure constant-time comparison
DUMMY_HASH = "$argon2id$v=19$m=65536,t=3,p=4$MjQyZWE1MzBjYjJlZTI0Yw$YTU4NGM5ZTZmYjE2NzZlZjY0ZWY3ZGRkY2U2OWFjNjk"


def authenticate(*, session: Session, email: str, password: str) -> User | None:
    db_user = get_user_by_email(session=session, email=email)
    if not db_user:
        # Prevent timing attacks by running password verification even when user doesn't exist
        # This ensures the response time is similar whether or not the email exists
        verify_password(password, DUMMY_HASH)
        return None
    verified, updated_password_hash = verify_password(password, db_user.hashed_password)
    if not verified:
        return None
    if updated_password_hash:
        db_user.hashed_password = updated_password_hash
        session.add(db_user)
        session.commit()
        session.refresh(db_user)
    return db_user


def create_item(*, session: Session, item_in: ItemCreate, owner_id: uuid.UUID) -> Item:
    db_item = Item.model_validate(item_in, update={"owner_id": owner_id})
    session.add(db_item)
    session.commit()
    session.refresh(db_item)
    return db_item


def create_product(*, session: Session, product_in: ProductCreate) -> Product:
    db_product = Product.model_validate(product_in)
    session.add(db_product)
    session.commit()
    session.refresh(db_product)
    return db_product


def create_checkout_counter(
    *, session: Session, counter_in: CheckoutCounterCreate
) -> CheckoutCounter:
    db_obj = CheckoutCounter.model_validate(
        counter_in, update={"password_hash": get_password_hash(counter_in.password)}
    )
    session.add(db_obj)
    session.commit()
    session.refresh(db_obj)
    return db_obj


def update_checkout_counter(
    *, session: Session, db_counter: CheckoutCounter, counter_in: CheckoutCounterUpdate
) -> CheckoutCounter:
    counter_data = counter_in.model_dump(exclude_unset=True)
    extra_data = {}
    if "password" in counter_data:
        extra_data["password_hash"] = get_password_hash(counter_data.pop("password"))
    db_counter.sqlmodel_update(counter_data, update=extra_data)
    session.add(db_counter)
    session.commit()
    session.refresh(db_counter)
    return db_counter


def authenticate_checkout_counter(
    *, session: Session, counter_id: uuid.UUID, password: str
) -> CheckoutCounter | None:
    db_counter = session.get(CheckoutCounter, counter_id)
    if not db_counter:
        verify_password(password, DUMMY_HASH)
        return None
    verified, updated_password_hash = verify_password(password, db_counter.password_hash)
    if not verified:
        return None
    if updated_password_hash:
        db_counter.password_hash = updated_password_hash
        session.add(db_counter)
        session.commit()
        session.refresh(db_counter)
    return db_counter


def get_open_checkout_session(
    *, session: Session, counter_id: uuid.UUID, client_id: str
) -> CheckoutSession | None:
    statement = select(CheckoutSession).where(
        CheckoutSession.counter_id == counter_id,
        CheckoutSession.client_id == client_id,
        CheckoutSession.closed.is_(False),
    )
    return session.exec(statement).first()


def create_checkout_session(
    *, session: Session, counter_id: uuid.UUID, client_id: str
) -> CheckoutSession:
    db_obj = CheckoutSession(counter_id=counter_id, client_id=client_id)
    session.add(db_obj)
    session.commit()
    session.refresh(db_obj)
    return db_obj


def update_checkout_session_cart(
    *,
    session: Session,
    db_session: CheckoutSession,
    cart: list[CheckoutSessionCartItem],
) -> CheckoutSession:
    db_session.cart = [item.model_dump(mode="json") for item in cart]
    db_session.updated_at = get_datetime_utc()
    session.add(db_session)
    session.commit()
    session.refresh(db_session)
    return db_session


def close_checkout_session(
    *, session: Session, db_session: CheckoutSession
) -> CheckoutSession:
    now = get_datetime_utc()
    db_session.closed = True
    db_session.payment_status = CheckoutSessionPaymentStatus.paid
    db_session.updated_at = now
    db_session.closed_at = now
    session.add(db_session)
    session.commit()
    session.refresh(db_session)
    return db_session
