import logging
from typing import Annotated, Any
from uuid import UUID

from fastapi import APIRouter, Depends, Query, WebSocket, WebSocketDisconnect, status
from jwt.exceptions import InvalidTokenError
from sqlalchemy.orm import Session

from app.auth import utils as auth_utils
from app.core.errors import AppError
from app.db.session import get_db
from app.models.user import User
from app.services import auction as auction_service
from app.ws.auction import auction_ws_manager


router = APIRouter(prefix="/ws", tags=["websocket"])
logger = logging.getLogger(__name__)


def get_ws_user(token: str, db: Session) -> User | None:
    try:
        payload = auth_utils.decode_jwt(token)
    except InvalidTokenError:
        return None

    if payload.get("type") != "access":
        return None

    user_id = payload.get("sub")
    if user_id is None:
        return None

    try:
        user = db.get(User, UUID(user_id))
    except (TypeError, ValueError):
        return None

    if user is None or not user.is_active:
        return None

    return user


@router.websocket("/auctions/{auction_id}")
async def auction_websocket(
    websocket: WebSocket,
    auction_id: UUID,
    token: Annotated[str, Query()],
    db: Annotated[Session, Depends(get_db)],
) -> None:
    user = get_ws_user(token, db)
    if user is None:
        logger.warning(
            "websocket rejected",
            extra={
                "event": "websocket_rejected",
                "auction_id": str(auction_id),
                "reason": "invalid_token",
            },
        )
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
        return

    try:
        auction = auction_service.get_auction(db, auction_id)
    except AppError:
        logger.warning(
            "websocket rejected",
            extra={
                "event": "websocket_rejected",
                "auction_id": str(auction_id),
                "user_id": str(user.id),
                "reason": "auction_unavailable",
            },
        )
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
        return

    await auction_ws_manager.connect(auction_id, websocket)
    logger.info(
        "websocket connected",
        extra={
            "event": "websocket_connected",
            "auction_id": str(auction_id),
            "user_id": str(user.id),
        },
    )

    try:
        await websocket.send_json(
            {
                "type": "connected",
                "auction_id": str(auction_id),
                "user_id": str(user.id),
            }
        )
        await websocket.send_json(
            {
                "type": "auction_snapshot",
                "auction": auction.model_dump(mode="json"),
            }
        )

        while True:
            message: dict[str, Any] = await websocket.receive_json()
            message_type = message.get("type")

            if message_type == "ping":
                await websocket.send_json({"type": "pong"})
            else:
                await websocket.send_json(
                    {
                        "type": "error",
                        "code": "unknown_message_type",
                        "message": "This websocket only supports ping from clients",
                    }
                )
    except WebSocketDisconnect:
        auction_ws_manager.disconnect(auction_id, websocket)
        logger.info(
            "websocket disconnected",
            extra={
                "event": "websocket_disconnected",
                "auction_id": str(auction_id),
                "user_id": str(user.id),
                "reason": "client_disconnect",
            },
        )
    except RuntimeError:
        auction_ws_manager.disconnect(auction_id, websocket)
        logger.warning(
            "websocket disconnected",
            extra={
                "event": "websocket_disconnected",
                "auction_id": str(auction_id),
                "user_id": str(user.id),
                "reason": "runtime_error",
            },
        )
