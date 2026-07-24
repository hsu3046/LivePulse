from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import Awaitable, Callable

from fastapi import WebSocket


@dataclass(eq=False)
class Client:
    websocket: WebSocket
    event_id: str
    role: str
    participant_id: str | None = None


SnapshotBuilder = Callable[[str, str, str | None], dict]


class ConnectionManager:
    def __init__(self) -> None:
        self._clients: dict[str, set[Client]] = {}
        self._lock = asyncio.Lock()

    async def connect(
        self,
        websocket: WebSocket,
        event_id: str,
        role: str,
        participant_id: str | None = None,
    ) -> Client:
        await websocket.accept()
        client = Client(websocket, event_id, role, participant_id)
        async with self._lock:
            self._clients.setdefault(event_id, set()).add(client)
        return client

    async def disconnect(self, client: Client) -> None:
        async with self._lock:
            clients = self._clients.get(client.event_id)
            if not clients:
                return
            clients.discard(client)
            if not clients:
                self._clients.pop(client.event_id, None)

    async def send_snapshot(self, client: Client, builder: SnapshotBuilder) -> None:
        snapshot = builder(client.event_id, client.role, client.participant_id)
        await client.websocket.send_json({"type": "STATE_SNAPSHOT", "state": snapshot})

    async def broadcast_snapshots(
        self,
        event_id: str,
        builder: SnapshotBuilder,
        roles: set[str] | None = None,
    ) -> None:
        async with self._lock:
            clients = list(self._clients.get(event_id, set()))

        stale: list[Client] = []
        for client in clients:
            if roles is not None and client.role not in roles:
                continue
            try:
                snapshot = builder(client.event_id, client.role, client.participant_id)
                await client.websocket.send_json({"type": "STATE_SNAPSHOT", "state": snapshot})
            except Exception:
                stale.append(client)

        for client in stale:
            await self.disconnect(client)

    def connected_participants(self, event_id: str) -> int:
        clients = self._clients.get(event_id, set())
        return len(
            {
                client.participant_id
                for client in clients
                if client.role == "participant" and client.participant_id
            }
        )


manager = ConnectionManager()
