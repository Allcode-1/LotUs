from app.models.user import UserRole
from tests.helpers import (
    assert_error_code,
    create_item,
    create_user_with_token,
    money,
    png_bytes,
    top_up_balance,
)


def test_user_can_create_item_and_admin_can_top_up_balance(client, db_session):
    user, _tokens, user_headers = create_user_with_token(client, "item_owner")
    _admin, _admin_tokens, admin_headers = create_user_with_token(
        client,
        "balance_admin",
        db_session,
        role=UserRole.ADMIN,
    )

    item = create_item(client, user_headers, title="Omega Watch")
    assert item["title"] == "Omega Watch"
    assert item["owner_id"] == user["id"]
    assert item["status"] == "available"
    assert item["images"][0]["url"].startswith("https://storage.test/items/")

    my_items_response = client.get("/api/v1/items/me", headers=user_headers)
    assert my_items_response.status_code == 200, my_items_response.text
    assert [my_item["id"] for my_item in my_items_response.json()] == [item["id"]]

    balance = top_up_balance(client, admin_headers, user["id"], amount="250.00")
    assert money(balance["amount"]) == money("250.00")
    assert money(balance["reserved_amount"]) == money("0.00")
    assert money(balance["available_amount"]) == money("250.00")

    forbidden_response = client.post(
        f"/api/v1/balance/users/{user['id']}/top-up",
        headers=user_headers,
        json={"amount": "10.00"},
    )
    assert forbidden_response.status_code == 403

    invalid_amount_response = client.post(
        f"/api/v1/balance/users/{user['id']}/top-up",
        headers=admin_headers,
        json={"amount": "0.00"},
    )
    assert invalid_amount_response.status_code == 422


def test_item_upload_rejects_invalid_image_payload(client):
    _user, _tokens, headers = create_user_with_token(client, "bad_image_owner")

    response = client.post(
        "/api/v1/items",
        headers=headers,
        data={"title": "Not really an image"},
        files=[("images", ("bad.txt", b"plain text", "text/plain"))],
    )
    assert response.status_code == 415
    assert_error_code(response, "unsupported_image_content_type")

    mismatch_response = client.post(
        "/api/v1/items",
        headers=headers,
        data={"title": "Wrong content type"},
        files=[("images", ("wrong.jpg", png_bytes(), "image/jpeg"))],
    )
    assert mismatch_response.status_code == 415
    assert_error_code(mismatch_response, "image_content_type_mismatch")
