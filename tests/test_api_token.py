import json

import pytest
from rest_framework.test import APIClient


@pytest.fixture
def client(settings):
    settings.OAUTH_CLIENT_ID = "client-id"
    settings.OAUTH_CLIENT_SECRET = "client-secret"
    settings.SECRET_KEY = "test-secret-1234567890abcdef1234567890abcdef"
    return APIClient()


def test_token_success(client):
    resp = client.post(
        "/api/token/",
        data={"grant_type": "client_credentials", "client_id": "client-id", "client_secret": "client-secret"},
        format="json",
    )
    assert resp.status_code == 200
    data = resp.json()
    assert "access_token" in data
    assert data["expires_in"] > 0


def test_token_invalid_key(client):
    resp = client.post(
        "/api/token/",
        data={"grant_type": "client_credentials", "client_id": "wrong", "client_secret": "wrong"},
        format="json",
    )
    assert resp.status_code == 401


def test_token_missing_params(client):
    resp = client.post("/api/token/", data={"grant_type": "client_credentials"}, format="json")
    assert resp.status_code == 400


def test_token_invalid_grant(client):
    resp = client.post(
        "/api/token/",
        data={"grant_type": "password", "client_id": "client-id", "client_secret": "client-secret"},
        format="json",
    )
    assert resp.status_code == 400
