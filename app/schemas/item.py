from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator


class ItemCreate(BaseModel):
    ...


class ItemRead(BaseModel):
    ...


class ItemUpdate(BaseModel):
    ...