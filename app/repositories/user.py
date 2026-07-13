from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.user import User


def get_users(
    db: Session,
    offset: int = 0,
    limit: int = 100,
) -> list[User]:
    users = select(User).order_by(User.id).offset(offset).limit(limit)
    return list(db.scalars(users).all())


def get_user(db: Session, user_id: UUID) -> User | None:
    return db.get(User, user_id)
