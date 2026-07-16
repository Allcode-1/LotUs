from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, BackgroundTasks, Depends, status
from sqlalchemy.orm import Session

from app.auth.dependencies import get_current_active_user
from app.cache.auction import AuctionCache
from app.cache.dependencies import get_auction_cache
from app.db.session import get_db
from app.models.auction import AuctionStatus
from app.models.user import User
from app.rate_limit import policies as rate_limit_policies
from app.rate_limit.dependencies import get_rate_limiter
from app.rate_limit.service import RateLimiter
from app.schemas.auction import AuctionCreate, AuctionRead, BidCreate, BidRead, LotRead
from app.services import auction as auction_service
from app.services import auction_query as auction_query_service
from app.services import auction_timers
from app.ws.auction import auction_ws_manager


router = APIRouter(prefix="/auctions", tags=["auctions"])


@router.post("", response_model=AuctionRead, status_code=status.HTTP_201_CREATED)
def create_auction(
    payload: AuctionCreate,
    db: Annotated[Session, Depends(get_db)],
    user: Annotated[User, Depends(get_current_active_user)],
) -> AuctionRead:
    return auction_service.create_auction(db, payload, user)


@router.get("", response_model=list[AuctionRead])
def get_auctions(
    db: Annotated[Session, Depends(get_db)],
    user: Annotated[User, Depends(get_current_active_user)],
    offset: int = 0,
    limit: int = 100,
) -> list[AuctionRead]:
    return auction_service.get_auctions(db, offset, limit)


@router.get("/me", response_model=list[AuctionRead])
def get_my_auctions(
    db: Annotated[Session, Depends(get_db)],
    user: Annotated[User, Depends(get_current_active_user)],
    offset: int = 0,
    limit: int = 100,
) -> list[AuctionRead]:
    return auction_service.get_my_auctions(db, user, offset, limit)


@router.get("/{auction_id}", response_model=AuctionRead)
def get_auction(
    auction_id: UUID,
    db: Annotated[Session, Depends(get_db)],
    user: Annotated[User, Depends(get_current_active_user)],
    auction_cache: Annotated[AuctionCache, Depends(get_auction_cache)],
) -> AuctionRead:
    return auction_query_service.get_auction(db, auction_cache, auction_id)


@router.post("/{auction_id}/start", response_model=AuctionRead)
def start_auction(
    auction_id: UUID,
    background_tasks: BackgroundTasks,
    db: Annotated[Session, Depends(get_db)],
    user: Annotated[User, Depends(get_current_active_user)],
    auction_cache: Annotated[AuctionCache, Depends(get_auction_cache)],
) -> AuctionRead:
    auction = auction_service.start_auction(db, auction_id, user)
    auction_cache.invalidate_auction(auction_id)
    background_tasks.add_task(
        auction_ws_manager.broadcast,
        auction_id,
        {
            "type": "auction_started",
            "auction": auction.model_dump(mode="json"),
        },
    )
    return auction


@router.post("/{auction_id}/cancel", response_model=AuctionRead)
def cancel_auction(
    auction_id: UUID,
    background_tasks: BackgroundTasks,
    db: Annotated[Session, Depends(get_db)],
    user: Annotated[User, Depends(get_current_active_user)],
    auction_cache: Annotated[AuctionCache, Depends(get_auction_cache)],
) -> AuctionRead:
    auction = auction_service.cancel_auction(db, auction_id, user)
    auction_cache.invalidate_auction(auction_id)
    background_tasks.add_task(
        auction_ws_manager.broadcast,
        auction_id,
        {
            "type": "auction_cancelled",
            "auction": auction.model_dump(mode="json"),
        },
    )
    return auction


@router.post("/{auction_id}/finish", response_model=AuctionRead)
def finish_auction(
    auction_id: UUID,
    background_tasks: BackgroundTasks,
    db: Annotated[Session, Depends(get_db)],
    user: Annotated[User, Depends(get_current_active_user)],
    auction_cache: Annotated[AuctionCache, Depends(get_auction_cache)],
) -> AuctionRead:
    auction = auction_service.finish_auction(db, auction_id, user)
    auction_cache.invalidate_auction(auction_id)
    background_tasks.add_task(
        auction_ws_manager.broadcast,
        auction_id,
        {
            "type": "auction_finished",
            "auction": auction.model_dump(mode="json"),
        },
    )
    return auction


@router.post("/{auction_id}/lots/{lot_id}/confirm-sale", response_model=LotRead)
def confirm_lot_sale(
    auction_id: UUID,
    lot_id: UUID,
    background_tasks: BackgroundTasks,
    db: Annotated[Session, Depends(get_db)],
    user: Annotated[User, Depends(get_current_active_user)],
    auction_cache: Annotated[AuctionCache, Depends(get_auction_cache)],
) -> LotRead:
    lot = auction_service.confirm_lot_sale(db, auction_id, lot_id, user)
    auction_cache.invalidate_auction(auction_id)
    auction = auction_service.get_auction(db, auction_id)
    background_tasks.add_task(
        auction_timers.broadcast_lot_sold,
        auction_id,
        lot,
    )
    if auction.status == AuctionStatus.FINISHED:
        background_tasks.add_task(
            auction_ws_manager.broadcast,
            auction_id,
            {
                "type": "auction_finished",
                "auction": auction.model_dump(mode="json"),
            },
        )
    return lot


@router.post(
    "/{auction_id}/lots/{lot_id}/bids",
    response_model=BidRead,
    status_code=status.HTTP_201_CREATED,
)
def place_bid(
    auction_id: UUID,
    lot_id: UUID,
    payload: BidCreate,
    background_tasks: BackgroundTasks,
    db: Annotated[Session, Depends(get_db)],
    user: Annotated[User, Depends(get_current_active_user)],
    rate_limiter: Annotated[RateLimiter, Depends(get_rate_limiter)],
    auction_cache: Annotated[AuctionCache, Depends(get_auction_cache)],
) -> BidRead:
    rate_limit_policies.check_bid_rate_limit(
        rate_limiter,
        user.id,
        auction_id,
        lot_id,
    )
    bid = auction_service.place_bid(db, auction_id, lot_id, payload, user)
    auction_cache.invalidate_auction(auction_id)
    lot = auction_service.get_lot(db, auction_id, lot_id)

    background_tasks.add_task(
        auction_ws_manager.broadcast,
        auction_id,
        {
            "type": "bid_placed",
            "auction_id": str(auction_id),
            "lot": lot.model_dump(mode="json"),
            "bid": bid.model_dump(mode="json"),
        },
    )

    if lot.sale_confirmable_at is not None:
        background_tasks.add_task(
            auction_timers.auto_confirm_lot_sale,
            auction_id,
            lot_id,
            lot.sale_confirmable_at,
        )

    return bid


@router.get("/{auction_id}/lots/{lot_id}/bids", response_model=list[BidRead])
def get_lot_bids(
    auction_id: UUID,
    lot_id: UUID,
    db: Annotated[Session, Depends(get_db)],
    user: Annotated[User, Depends(get_current_active_user)],
    offset: int = 0,
    limit: int = 100,
) -> list[BidRead]:
    return auction_service.get_lot_bids(db, auction_id, lot_id, offset, limit)
