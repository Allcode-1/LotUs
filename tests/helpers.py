from datetime import datetime, timedelta, timezone
from decimal import Decimal
from io import BytesIO
from uuid import UUID

from fastapi.testclient import TestClient
from PIL import Image
from sqlalchemy.orm import Session

from app.models.user import User, UserRole


DEFAULT_PASSWORD = "secret123"


def money(value: object) -> Decimal:
    return Decimal(str(value))


def png_bytes() -> bytes:
    buffer = BytesIO()
    Image.new("RGB", (1, 1), color="white").save(buffer, format="PNG")
    return buffer.getvalue()


def assert_error_code(response, code: str) -> None:
    assert response.json()["error"]["code"] == code


def register_user(
    client: TestClient,
    username: str,
    email: str | None = None,
    password: str = DEFAULT_PASSWORD,
) -> dict:
    response = client.post(
        "/api/v1/auth/register",
        json={
            "username": username,
            "email": email or f"{username}@example.com",
            "password": password,
        },
    )
    assert response.status_code == 201, response.text
    return response.json()


def login_user(
    client: TestClient,
    username: str,
    password: str = DEFAULT_PASSWORD,
) -> dict:
    response = client.post(
        "/api/v1/auth/login",
        data={"username": username, "password": password},
    )
    assert response.status_code == 200, response.text
    return response.json()


def auth_headers(tokens: dict) -> dict[str, str]:
    return {"Authorization": f"Bearer {tokens['access_token']}"}


def create_user_with_token(
    client: TestClient,
    username: str,
    db_session: Session | None = None,
    role: UserRole = UserRole.USER,
) -> tuple[dict, dict, dict[str, str]]:
    user = register_user(client, username)

    if role != UserRole.USER:
        if db_session is None:
            raise ValueError("db_session is required to promote a test user")
        user_model = db_session.get(User, UUID(user["id"]))
        assert user_model is not None
        user_model.role = role
        db_session.commit()

    tokens = login_user(client, username)
    return user, tokens, auth_headers(tokens)


def create_item(
    client: TestClient,
    headers: dict[str, str],
    title: str = "Test item",
    description: str | None = "Test item description",
) -> dict:
    data = {"title": title}
    if description is not None:
        data["description"] = description

    response = client.post(
        "/api/v1/items",
        headers=headers,
        data=data,
        files=[("images", ("item.png", png_bytes(), "image/png"))],
    )
    assert response.status_code == 201, response.text
    return response.json()


def auction_window() -> tuple[str, str]:
    now = datetime.now(timezone.utc)
    return (
        (now + timedelta(minutes=5)).isoformat(),
        (now + timedelta(hours=1)).isoformat(),
    )


def create_auction(
    client: TestClient,
    headers: dict[str, str],
    item_ids: list[str],
    title: str = "Test auction",
    min_bid_increment: str = "5.00",
    lot_start_price: str = "100.00",
    lot_min_bid_increment: str | None = None,
) -> dict:
    starts_at, ends_at = auction_window()
    response = client.post(
        "/api/v1/auctions",
        headers=headers,
        json={
            "title": title,
            "description": "Test auction description",
            "starts_at": starts_at,
            "ends_at": ends_at,
            "min_bid_increment": min_bid_increment,
            "lots": [
                {
                    "item_id": item_id,
                    "start_price": lot_start_price,
                    "min_bid_increment": lot_min_bid_increment,
                }
                for item_id in item_ids
            ],
        },
    )
    assert response.status_code == 201, response.text
    return response.json()


def start_auction(
    client: TestClient,
    headers: dict[str, str],
    auction_id: str,
) -> dict:
    response = client.post(f"/api/v1/auctions/{auction_id}/start", headers=headers)
    assert response.status_code == 200, response.text
    return response.json()


def top_up_balance(
    client: TestClient,
    admin_headers: dict[str, str],
    user_id: str,
    amount: str = "500.00",
) -> dict:
    response = client.post(
        f"/api/v1/balance/users/{user_id}/top-up",
        headers=admin_headers,
        json={"amount": amount},
    )
    assert response.status_code == 200, response.text
    return response.json()
