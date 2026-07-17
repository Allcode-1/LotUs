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


def test_item_owner_permissions_for_update_images_and_delete(client, db_session):
    _owner, _owner_tokens, owner_headers = create_user_with_token(
        client,
        "item_lifecycle_owner",
    )
    _stranger, _stranger_tokens, stranger_headers = create_user_with_token(
        client,
        "item_lifecycle_stranger",
    )

    item = create_item(client, owner_headers, title="Editable item")
    initial_image_id = item["images"][0]["id"]

    stranger_patch_response = client.patch(
        f"/api/v1/items/{item['id']}",
        headers=stranger_headers,
        json={"title": "Stolen title"},
    )
    assert stranger_patch_response.status_code == 403
    assert_error_code(stranger_patch_response, "item_permission_denied")

    owner_patch_response = client.patch(
        f"/api/v1/items/{item['id']}",
        headers=owner_headers,
        json={"title": "Updated item", "description": "Updated description"},
    )
    assert owner_patch_response.status_code == 200, owner_patch_response.text
    assert owner_patch_response.json()["title"] == "Updated item"
    assert owner_patch_response.json()["description"] == "Updated description"

    stranger_add_image_response = client.post(
        f"/api/v1/items/{item['id']}/images",
        headers=stranger_headers,
        files=[("images", ("extra.png", png_bytes(), "image/png"))],
    )
    assert stranger_add_image_response.status_code == 403
    assert_error_code(stranger_add_image_response, "item_permission_denied")

    owner_add_image_response = client.post(
        f"/api/v1/items/{item['id']}/images",
        headers=owner_headers,
        files=[("images", ("extra.png", png_bytes(), "image/png"))],
    )
    assert owner_add_image_response.status_code == 201, owner_add_image_response.text
    added_image = owner_add_image_response.json()[0]
    assert added_image["sort_order"] == 1
    assert added_image["is_primary"] is False

    stranger_delete_image_response = client.delete(
        f"/api/v1/items/{item['id']}/images/{added_image['id']}",
        headers=stranger_headers,
    )
    assert stranger_delete_image_response.status_code == 403
    assert_error_code(stranger_delete_image_response, "item_permission_denied")

    owner_delete_image_response = client.delete(
        f"/api/v1/items/{item['id']}/images/{added_image['id']}",
        headers=owner_headers,
    )
    assert owner_delete_image_response.status_code == 204
    db_session.expire_all()

    images_response = client.get(
        f"/api/v1/items/{item['id']}/images", headers=owner_headers
    )
    assert images_response.status_code == 200, images_response.text
    assert [image["id"] for image in images_response.json()] == [initial_image_id]

    stranger_delete_item_response = client.delete(
        f"/api/v1/items/{item['id']}",
        headers=stranger_headers,
    )
    assert stranger_delete_item_response.status_code == 403
    assert_error_code(stranger_delete_item_response, "item_permission_denied")

    owner_delete_item_response = client.delete(
        f"/api/v1/items/{item['id']}",
        headers=owner_headers,
    )
    assert owner_delete_item_response.status_code == 204

    deleted_item_response = client.get(
        f"/api/v1/items/{item['id']}", headers=owner_headers
    )
    assert deleted_item_response.status_code == 404
    assert_error_code(deleted_item_response, "item_not_found")
