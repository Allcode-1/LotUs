from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


# create schema not needed
# class BalanceCreate(BaseModel):
#     user_id: UUID
#     amount: Decimal


class BalanceRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    user_id: UUID
    amount: Decimal
    reserved_amount: Decimal
    available_amount: Decimal


class BalanceUpdate(BaseModel):
    amount: Decimal = Field(gt=0)
