import asyncio
import json
import uuid
from typing import Any

from fastapi import APIRouter, HTTPException, WebSocket, WebSocketDisconnect
from pydantic import ValidationError
from sqlmodel import Session

from app import crud
from app.core.api_keys import authenticate_checkout_counter_api_key
from app.core.db import engine
from app.core.ws_manager import manager
from app.models import (
    CheckoutCameraReport,
    CheckoutCounter,
    CheckoutSession,
    CheckoutSessionCartItem,
    CheckoutSessionPublic,
    Product,
    ProductUnit,
)

router = APIRouter(prefix="/ws", tags=["ws"])

HEARTBEAT_INTERVAL_SECONDS = 5.0


def _session_state_payload(public: CheckoutSessionPublic) -> dict[str, Any]:
    return {
        "type": "session_state",
        "session": public.model_dump(mode="json"),
        "admin_takeover": manager.is_admin_present(public.id),
    }


async def _broadcast_state_for_session(session_id: uuid.UUID) -> None:
    with Session(engine) as session:
        checkout_session = session.get(CheckoutSession, session_id)
        if not checkout_session:
            return
        public = CheckoutSessionPublic.from_db(checkout_session)
    await manager.broadcast(session_id, _session_state_payload(public))


@router.websocket("/checkout-session")
async def checkout_session_ws(
    websocket: WebSocket,
) -> None:
    await websocket.accept()

    with Session(engine) as session:
        try:
            _, counter = authenticate_checkout_counter_api_key(
                session,
                websocket.headers.get("X-API-Key", ""),
                "checkout:session",
            )
        except HTTPException:
            await websocket.send_json({"type": "error", "code": "auth_failed"})
            await websocket.close(code=4401)
            return

        checkout_session = crud.get_open_checkout_session(
            session=session, counter_id=counter.id
        )
        if not checkout_session:
            checkout_session = crud.create_checkout_session(
                session=session, counter_id=counter.id
            )

        public = CheckoutSessionPublic.from_db(checkout_session)
        session_id = checkout_session.id

    await websocket.send_json(_session_state_payload(public))
    await manager.register_client(session_id, websocket)

    heartbeat_task = asyncio.create_task(_send_heartbeat(websocket))
    try:
        while True:
            raw_payload = await websocket.receive_text()
            try:
                payload = json.loads(raw_payload)
            except json.JSONDecodeError:
                continue
            if not isinstance(payload, dict):
                continue
            if payload.get("type") != "available_cameras":
                continue
            try:
                report = CheckoutCameraReport.model_validate(payload)
            except ValidationError:
                await websocket.send_json(
                    {"type": "error", "code": "invalid_camera_report"}
                )
                continue
            with Session(engine) as session:
                db_counter = session.get(CheckoutCounter, counter.id)
                if db_counter is not None and report.camera_discovery_succeeded:
                    crud.update_checkout_counter_cameras(
                        session=session,
                        db_counter=db_counter,
                        cameras=report.available_cameras,
                    )
    except WebSocketDisconnect:
        pass
    except Exception:
        pass
    finally:
        heartbeat_task.cancel()
        await manager.unregister_client(session_id, websocket)


@router.websocket("/admin/sessions/{session_id}")
async def admin_session_ws(
    websocket: WebSocket,
    session_id: uuid.UUID,
    token: str,
) -> None:
    await websocket.accept()

    if not _verify_admin_token(token):
        await websocket.send_json({"type": "error", "code": "auth_failed"})
        await websocket.close(code=4401)
        return

    with Session(engine) as session:
        checkout_session = session.get(CheckoutSession, session_id)
        if not checkout_session:
            await websocket.send_json({"type": "error", "code": "session_not_found"})
            await websocket.close(code=4404)
            return
        public = CheckoutSessionPublic.from_db(checkout_session)

    await manager.register_admin(session_id, websocket)
    await websocket.send_json(_session_state_payload(public))
    # Notify everyone (including the freshly-arrived admin and the client)
    # that admin presence changed.
    await _broadcast_state_for_session(session_id)

    heartbeat_task = asyncio.create_task(_send_heartbeat(websocket))
    try:
        while True:
            payload = await websocket.receive_json()
            if not _verify_admin_token(token):
                await websocket.close(code=4401)
                break
            await _handle_admin_command(session_id, payload)
    except WebSocketDisconnect:
        pass
    except Exception:
        pass
    finally:
        heartbeat_task.cancel()
        await manager.unregister_admin(session_id, websocket)
        await _broadcast_state_for_session(session_id)


def _verify_admin_token(token: str) -> bool:
    from fastapi import HTTPException

    from app.api.deps import get_current_user

    try:
        with Session(engine) as session:
            return get_current_user(session, token).is_superuser
    except HTTPException, ValueError:
        return False


async def _handle_admin_command(session_id: uuid.UUID, payload: dict[str, Any]) -> None:
    command = payload.get("command")
    if command == "remove_item":
        index = payload.get("index")
        if not isinstance(index, int):
            return
        await _remove_cart_item(session_id, index)
    elif command == "update_item_quantity":
        index = payload.get("index")
        quantity = payload.get("quantity")
        if not isinstance(index, int):
            return
        if not isinstance(quantity, (int, float)) or quantity <= 0:
            return
        await _update_cart_item_quantity(session_id, index, float(quantity))
    elif command == "add_item":
        product_id_raw = payload.get("product_id")
        quantity = payload.get("quantity")
        if not isinstance(product_id_raw, str):
            return
        try:
            product_id = uuid.UUID(product_id_raw)
        except ValueError:
            return
        if not isinstance(quantity, (int, float)) or quantity <= 0:
            return
        await _add_cart_item(session_id, product_id, float(quantity))
    elif command == "cancel_session":
        await _cancel_session(session_id)


async def _remove_cart_item(session_id: uuid.UUID, index: int) -> None:
    with Session(engine) as session:
        checkout_session = session.get(CheckoutSession, session_id)
        if not checkout_session or checkout_session.closed:
            return
        cart_items = [
            CheckoutSessionCartItem.model_validate(item)
            for item in checkout_session.cart or []
        ]
        if index < 0 or index >= len(cart_items):
            return
        cart_items.pop(index)
        checkout_session = crud.update_checkout_session_cart(
            session=session, db_session=checkout_session, cart=cart_items
        )
        public = CheckoutSessionPublic.from_db(checkout_session)
    await manager.broadcast(session_id, _session_state_payload(public))


def _format_quantity_label(unit: ProductUnit, quantity: float) -> str:
    if unit == ProductUnit.kg:
        return f"{quantity:.2f} kg"
    return f"{int(quantity)} szt"


async def _add_cart_item(
    session_id: uuid.UUID, product_id: uuid.UUID, quantity: float
) -> None:
    with Session(engine) as session:
        checkout_session = session.get(CheckoutSession, session_id)
        if not checkout_session or checkout_session.closed:
            return
        product = session.get(Product, product_id)
        if not product:
            return
        if product.unit == ProductUnit.pcs:
            quantity = float(int(quantity))
            if quantity <= 0:
                return
        else:
            quantity = round(quantity, 3)
        price = float(product.price)
        item = CheckoutSessionCartItem(
            product_id=product.id,
            name=product.name,
            unit=product.unit,
            price=price,
            quantity=quantity,
            quantity_label=_format_quantity_label(product.unit, quantity),
            line_total=round(quantity * price, 2),
            image_url=product.thumbnail_url or product.image_url,
        )
        cart_items = [
            CheckoutSessionCartItem.model_validate(existing)
            for existing in checkout_session.cart or []
        ]
        cart_items.append(item)
        checkout_session = crud.update_checkout_session_cart(
            session=session, db_session=checkout_session, cart=cart_items
        )
        public = CheckoutSessionPublic.from_db(checkout_session)
    await manager.broadcast(session_id, _session_state_payload(public))


async def _update_cart_item_quantity(
    session_id: uuid.UUID, index: int, quantity: float
) -> None:
    with Session(engine) as session:
        checkout_session = session.get(CheckoutSession, session_id)
        if not checkout_session or checkout_session.closed:
            return
        cart_items = [
            CheckoutSessionCartItem.model_validate(item)
            for item in checkout_session.cart or []
        ]
        if index < 0 or index >= len(cart_items):
            return
        item = cart_items[index]
        if item.unit == "kg":
            quantity = round(quantity, 3)
            quantity_label = f"{quantity:.2f} kg"
        else:
            quantity = float(int(quantity))
            if quantity <= 0:
                return
            quantity_label = f"{int(quantity)} szt"
        item.quantity = quantity
        item.quantity_label = quantity_label
        item.line_total = round(quantity * item.price, 2)
        cart_items[index] = item
        checkout_session = crud.update_checkout_session_cart(
            session=session, db_session=checkout_session, cart=cart_items
        )
        public = CheckoutSessionPublic.from_db(checkout_session)
    await manager.broadcast(session_id, _session_state_payload(public))


async def _cancel_session(session_id: uuid.UUID) -> None:
    with Session(engine) as session:
        checkout_session = session.get(CheckoutSession, session_id)
        if not checkout_session or checkout_session.closed:
            return
        checkout_session = crud.close_checkout_session(
            session=session, db_session=checkout_session
        )
        public = CheckoutSessionPublic.from_db(checkout_session)
    await manager.broadcast(session_id, _session_state_payload(public))
    # Closed sessions cannot be modified — drop client WS so it reconnects
    # and gets a freshly-created open session under a new session_id.
    await manager.disconnect_clients(session_id)


async def _send_heartbeat(websocket: WebSocket) -> None:
    try:
        while True:
            await asyncio.sleep(HEARTBEAT_INTERVAL_SECONDS)
            await websocket.send_json({"type": "ping"})
    except asyncio.CancelledError:
        return
    except Exception:
        return
