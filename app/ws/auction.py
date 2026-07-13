from collections import defaultdict
from uuid import UUID

from fastapi import WebSocket
from starlette.websockets import WebSocketState


class AuctionConnectionManager:
    def __init__(self) -> None:
        self._connections: dict[UUID, set[WebSocket]] = defaultdict(set)

    async def connect(self, auction_id: UUID, websocket: WebSocket) -> None:
        await websocket.accept()
        self._connections[auction_id].add(websocket)

    def disconnect(self, auction_id: UUID, websocket: WebSocket) -> None:
        connections = self._connections.get(auction_id)
        if connections is None:
            return

        connections.discard(websocket)
        if not connections:
            self._connections.pop(auction_id, None)

    async def broadcast(self, auction_id: UUID, message: dict) -> None:
        connections = list(self._connections.get(auction_id, set()))

        for websocket in connections:
            try:
                if websocket.client_state != WebSocketState.CONNECTED:
                    self.disconnect(auction_id, websocket)
                    continue

                await websocket.send_json(message)
            except RuntimeError:
                self.disconnect(auction_id, websocket)


auction_ws_manager = AuctionConnectionManager()
