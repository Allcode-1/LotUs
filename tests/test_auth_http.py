from tests.helpers import (
    DEFAULT_PASSWORD,
    auth_headers,
    create_user_with_token,
    money,
    register_user,
)


def test_register_login_refresh_logout_and_me(client):
    user = register_user(client, "alice")

    login_response = client.post(
        "/api/v1/auth/login",
        data={"username": "alice", "password": DEFAULT_PASSWORD},
    )
    assert login_response.status_code == 200, login_response.text
    tokens = login_response.json()
    assert tokens["token_type"] == "Bearer"
    assert tokens["access_token"]
    assert tokens["refresh_token"]

    me_response = client.get("/api/v1/auth/users/me", headers=auth_headers(tokens))
    assert me_response.status_code == 200, me_response.text
    assert me_response.json()["id"] == user["id"]

    balance_response = client.get("/api/v1/balance/me", headers=auth_headers(tokens))
    assert balance_response.status_code == 200, balance_response.text
    assert money(balance_response.json()["amount"]) == money("0.00")
    assert money(balance_response.json()["reserved_amount"]) == money("0.00")
    assert money(balance_response.json()["available_amount"]) == money("0.00")

    refresh_response = client.post(
        "/api/v1/auth/refresh",
        json={"refresh_token": tokens["refresh_token"]},
    )
    assert refresh_response.status_code == 200, refresh_response.text
    refreshed_tokens = refresh_response.json()
    assert refreshed_tokens["access_token"]
    assert refreshed_tokens["refresh_token"] != tokens["refresh_token"]

    reused_refresh_response = client.post(
        "/api/v1/auth/refresh",
        json={"refresh_token": tokens["refresh_token"]},
    )
    assert reused_refresh_response.status_code == 401

    logout_response = client.post(
        "/api/v1/auth/logout",
        json={"refresh_token": refreshed_tokens["refresh_token"]},
    )
    assert logout_response.status_code == 200, logout_response.text
    assert logout_response.json() == {"message": "Logged out"}


def test_auth_rejects_duplicate_registration_invalid_login_and_missing_token(client):
    create_user_with_token(client, "bob")

    duplicate_response = client.post(
        "/api/v1/auth/register",
        json={
            "username": "bob",
            "email": "bob-copy@example.com",
            "password": DEFAULT_PASSWORD,
        },
    )
    assert duplicate_response.status_code == 409
    assert duplicate_response.json()["detail"] == "Username or email are already taken"

    invalid_login_response = client.post(
        "/api/v1/auth/login",
        data={"username": "bob", "password": "wrong-password"},
    )
    assert invalid_login_response.status_code == 401

    missing_token_response = client.get("/api/v1/balance/me")
    assert missing_token_response.status_code == 401
