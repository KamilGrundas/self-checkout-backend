import asyncio
import uuid
from collections import defaultdict
from typing import Any

from fastapi import WebSocket


class CheckoutWsManager:
    def __init__(self) -> None:
        self._clients: dict[uuid.UUID, set[WebSocket]] = defaultdict(set)
        self._admins: dict[uuid.UUID, set[WebSocket]] = defaultdict(set)
        self._lock = asyncio.Lock()

    async def register_client(
        self, session_id: uuid.UUID, websocket: WebSocket
    ) -> None:
        async with self._lock:
            self._clients[session_id].add(websocket)

    async def unregister_client(
        self, session_id: uuid.UUID, websocket: WebSocket
    ) -> None:
        async with self._lock:
            sockets = self._clients.get(session_id)
            if not sockets:
                return
            sockets.discard(websocket)
            if not sockets:
                self._clients.pop(session_id, None)

    async def register_admin(self, session_id: uuid.UUID, websocket: WebSocket) -> None:
        async with self._lock:
            self._admins[session_id].add(websocket)

    async def unregister_admin(
        self, session_id: uuid.UUID, websocket: WebSocket
    ) -> None:
        async with self._lock:
            sockets = self._admins.get(session_id)
            if not sockets:
                return
            sockets.discard(websocket)
            if not sockets:
                self._admins.pop(session_id, None)

    def is_admin_present(self, session_id: uuid.UUID) -> bool:
        return bool(self._admins.get(session_id))

    async def disconnect_clients(self, session_id: uuid.UUID) -> None:
        async with self._lock:
            sockets = list(self._clients.get(session_id, ()))
        for socket in sockets:
            try:
                await socket.close()
            except Exception:
                pass
            await self.unregister_client(session_id, socket)

    async def broadcast(
        self,
        session_id: uuid.UUID,
        payload: dict[str, Any],
        *,
        to_clients: bool = True,
        to_admins: bool = True,
    ) -> None:
        async with self._lock:
            targets: list[WebSocket] = []
            if to_clients:
                targets.extend(self._clients.get(session_id, ()))
            if to_admins:
                targets.extend(self._admins.get(session_id, ()))
        for socket in targets:
            try:
                await socket.send_json(payload)
            except Exception:
                await self.unregister_client(session_id, socket)
                await self.unregister_admin(session_id, socket)


manager = CheckoutWsManager()
