from __future__ import annotations

from flask import Flask
from flask.testing import FlaskClient

from src.backend.auth import issue_token

def login_as(client: FlaskClient, username: str, password: str):
    """Perform a login request in tests and return the response."""
    response = client.post("/api/login", json={"username": username, "password": password})
    return response


def mint_access_token(app: Flask, user_id: str, **extra_claims) -> str:
    """Mint a signed access token for the given user id."""
    with app.app_context():
        return issue_token(user_id, extra=extra_claims or None)


def authenticate_client(app: Flask, client: FlaskClient, user_id: str, **extra_claims) -> None:
    """Attach a valid access token to the provided test client."""
    token = mint_access_token(app, user_id, **extra_claims)
    client.set_cookie("access_token", token, path="/")
