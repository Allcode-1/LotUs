from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, Field


# create schema not needed
# class BalanceCreate(BaseModel):
#     user_id: UUID
#     amount: Decimal


class BalanceRead(BaseModel):
    id: UUID
    user_id: UUID
    amount: Decimal


class BalanceUpdate(BaseModel):
    amount: Decimal = Field(gt=0)