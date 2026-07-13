from typing import Annotated

from fastapi import Form

from app.schemas.item import ItemCreate


def item_create_form(
    title: Annotated[str, Form()],
    description: Annotated[str | None, Form()] = None,
) -> ItemCreate:
    return ItemCreate(
        title=title,
        description=description,
    )
