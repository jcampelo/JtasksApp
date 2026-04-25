# tests/conftest.py
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from main import app
from app.services.approval_service import OWNER_EMAIL


def _make_service_mock():
    """
    Cria um MagicMock que simula o service_client do Supabase.
    Qualquer cadeia .table().select().eq()...execute() retorna .data = [].
    """
    mock = MagicMock()
    # Garante que .execute().data == [] em qualquer cadeia de chamadas
    mock.table.return_value.select.return_value.eq.return_value \
        .eq.return_value.limit.return_value.execute.return_value.data = []
    mock.table.return_value.select.return_value.eq.return_value \
        .execute.return_value.data = []
    mock.table.return_value.select.return_value.in_.return_value \
        .execute.return_value.data = []
    mock.table.return_value.select.return_value \
        .execute.return_value.data = []
    mock.table.return_value.select.return_value.eq.return_value \
        .gte.return_value.execute.return_value.data = []
    mock.table.return_value.select.return_value.eq.return_value \
        .order.return_value.execute.return_value.data = []
    mock.table.return_value.select.return_value.in_.return_value \
        .eq.return_value.execute.return_value.data = []
    return mock


@pytest.fixture(autouse=True)
def mock_service_client():
    """
    Patch global: impede chamadas de rede ao Supabase em todos os testes.

    Patcheia em cada módulo importador (não no fonte) porque Python vincula
    o nome no namespace do importador no momento do 'from x import y'.
    """
    svc_mock = _make_service_mock()
    _PATCH_TARGETS = [
        "app.services.monitoring_service.get_service_client",
        "app.services.permissions_service.get_service_client",
        "app.services.approval_service.get_service_client",
        "app.services.session_service.get_service_client",
    ]
    patches = [patch(t, return_value=svc_mock) for t in _PATCH_TARGETS]
    for p in patches:
        p.start()
    yield
    for p in patches:
        p.stop()


@pytest.fixture
def client(mock_service_client):
    with (
        patch("main.start_scheduler"),
        patch("main.stop_scheduler"),
        TestClient(app, raise_server_exceptions=False) as c,
    ):
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
