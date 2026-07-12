from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy.orm import Session

from app.auth.dependencies import get_current_active_user
from app.db.session import get_db
from app.models.user import User
from app.schemas.item import (
    ItemCreate,
    ItemRead,
    ItemUpdate,
)
from app.services import item as item_service
from app.services.item import ItemNotFoundError


router = APIRouter(prefix="/items", tags=["items"])
DbSession = Annotated[Session, Depends(get_db)]
CurrentUser = Annotated[User, Depends(get_current_active_user)]


def not_found_error(error: ItemNotFoundError) -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail=str(error),
    )


@router.post(
    "",
    response_model=ItemRead,
    status_code=status.HTTP_201_CREATED,
)
def add_item(
    payload: ItemCreate,
    db: DbSession,
    user: CurrentUser,
) -> ItemRead:
    item = item_service.add_item(db, payload)
    return ItemRead.model_validate(item)


@router.get("", response_model=list[ItemRead])
def get_items(
    db: DbSession,
    user: CurrentUser,
    offset: Annotated[int, Query(ge=0)] = 0,
    limit: Annotated[int, Query(ge=1, le=100)] = 100,
) -> list[ItemRead]:
    items = item_service.get_items(
        db,
        offset=offset,
        limit=limit,
    )
    return [ItemRead.model_validate(item) for item in items]


@router.get("/{item_id}", response_model=ItemRead)
def get_item(
    item_id: int,
    db: DbSession,
    user: CurrentUser,
) -> ItemRead:
    try:
        item = item_service.get_item(db, item_id)
        return ItemRead.model_validate(item)
    except ItemNotFoundError as error:
        raise not_found_error(error) from error


@router.patch("/{item_id}", response_model=ItemRead)
def patch_item(
    item_id: int,
    payload: ItemUpdate,
    db: DbSession,
    user: CurrentUser,
) -> ItemRead:
    try:
        item = item_service.patch_item(db, item_id, payload)
        return ItemRead.model_validate(item)
    except ItemNotFoundError as error:
        raise not_found_error(error) from error


@router.delete(
    "/{item_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    response_class=Response,
)
def delete_item(item_id: int, db: DbSession, user: CurrentUser) -> Response:
    try:
        item_service.delete_item(db, item_id)
    except ItemNotFoundError as error:
        raise not_found_error(error) from error

    return Response(status_code=status.HTTP_204_NO_CONTENT)
