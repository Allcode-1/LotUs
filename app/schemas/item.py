from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.models.item import ItemStatus


class ItemCreate(BaseModel):
    title: str = Field(min_length=1, max_length=55)
    description: str | None = Field(default=None, max_length=255)


class ItemUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=55)
    description: str | None = Field(default=None, max_length=255)


class ItemImageRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    item_id: UUID
    storage_key: str
    content_type: str
    size_bytes: int
    is_primary: bool
    sort_order: int
    created_at: datetime
    url: str


class ItemRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    title: str
    description: str | None
    creator_id: UUID
    owner_id: UUID
    status: ItemStatus
    created_at: datetime
    updated_at: datetime
    images: list[ItemImageRead] = Field(default_factory=list)
