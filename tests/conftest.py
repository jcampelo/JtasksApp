# tests/conftest.py
import pytest
from fastapi.testclient import TestClient

from main import app
from app.services.approval_service import OWNER_EMAIL


@pytest.fixture
def client():
    with TestClient(app, raise_server_exceptions=False) as c:
        yield c


@pytest.fixture
def owner_user():
    return {
        "user_id": "owner-uuid-0000-0000-000000000000",
        "email": OWNER_EMAIL,
        "access_token": "fake-token",
        "refresh_token": "fake-refresh",
        "expires_at": 9_999_999_999,
    }


@pytest.fixture
def regular_user():
    return {
        "user_id": "other-uuid-0000-0000-000000000000",
        "email": "outro@example.com",
        "access_token": "fake-token",
        "refresh_token": "fake-refresh",
        "expires_at": 9_999_999_999,
    }
