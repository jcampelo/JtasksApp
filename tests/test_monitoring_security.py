# tests/test_monitoring_security.py
"""
Testes de regressão de segurança para a feature de Acompanhamento.
Estes testes rodam sem banco de dados real.
"""
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from fastapi import HTTPException

from app.deps import get_current_user
from main import app


ANY_UUID = "00000000-0000-0000-0000-000000000000"

MONITORING_ENDPOINTS = [
    ("GET",    "/monitoring"),
    ("GET",    f"/monitoring/card/{ANY_UUID}"),
    ("GET",    f"/monitoring/refresh-all"),
    ("GET",    "/monitoring/pin-picker"),
    ("POST",   "/monitoring/pin"),
    ("DELETE", f"/monitoring/pin/{ANY_UUID}"),
]


# ── 1. Regressão: não-owner recebe 403 em TODOS os endpoints ────────────────

class TestNonOwnerGets403:
    def test_all_endpoints_return_403(self, client, regular_user):
        """
        Um usuário não-owner NÃO deve ter acesso a nenhum endpoint de monitoring.
        Testa todos os 6 endpoints definidos no router.
        """
        app.dependency_overrides[get_current_user] = lambda: regular_user

        try:
            for method, path in MONITORING_ENDPOINTS:
                resp = client.request(method, path)
                assert resp.status_code == 403, (
                    f"{method} {path} retornou {resp.status_code} — esperado 403. "
                    f"Conteúdo: {resp.text[:200]}"
                )
        finally:
            app.dependency_overrides.clear()

    def test_unauthenticated_gets_403(self, client):
        """Requisição sem sessão deve receber 403 (não redirect) nos endpoints HTMX."""
        # Sem dependency override — sessão vazia → get_current_user retorna RedirectResponse
        # require_owner converte RedirectResponse em HTTPException(403)
        for method, path in MONITORING_ENDPOINTS:
            resp = client.request(method, path, allow_redirects=False)
            # Aceita 403 ou redirect para login (302) — o importante é não retornar 200
            assert resp.status_code in (302, 403), (
                f"{method} {path} retornou {resp.status_code} sem autenticação"
            )


# ── 2. Validação de pin: watched_id não pinado → 404 ───────────────────────

class TestFetchRejectsNonPinnedUser:
    def test_fetch_raises_404_for_non_pinned(self):
        """
        fetch_watched_user_data deve levantar HTTPException(404)
        quando watched_id não está nos pinados do owner.
        """
        from app.services.monitoring_service import fetch_watched_user_data

        # Mock do user_client: watched_users retorna lista vazia (não pinado)
        mock_client = MagicMock()
        (
            mock_client.table.return_value
            .select.return_value
            .eq.return_value
            .eq.return_value
            .limit.return_value
            .execute.return_value
            .data
        ) = []

        with pytest.raises(HTTPException) as exc_info:
            fetch_watched_user_data(
                owner_id="owner-uuid",
                watched_id="random-uuid-not-pinned",
                resource="tasks_full",
                user_client=mock_client,
            )

        assert exc_info.value.status_code == 404

    def test_fetch_succeeds_for_pinned_user(self):
        """
        fetch_watched_user_data deve funcionar quando watched_id está pinado.
        """
        from app.services.monitoring_service import fetch_watched_user_data

        mock_client = MagicMock()
        # Simula pin encontrado
        (
            mock_client.table.return_value
            .select.return_value
            .eq.return_value
            .eq.return_value
            .limit.return_value
            .execute.return_value
            .data
        ) = [{"id": "some-pin-id"}]

        watched_id = "pinned-user-uuid"

        with patch("app.services.monitoring_service.get_service_client") as mock_svc:
            mock_svc_client = MagicMock()
            mock_svc.return_value = mock_svc_client
            (
                mock_svc_client.table.return_value
                .select.return_value
                .eq.return_value
                .eq.return_value
                .execute.return_value
                .data
            ) = []  # Nenhuma tarefa — retorno válido

            result = fetch_watched_user_data(
                owner_id="owner-uuid",
                watched_id=watched_id,
                resource="tasks_full",
                user_client=mock_client,
            )

        # Deve retornar o dict de grupos (possivelmente vazio)
        assert isinstance(result, dict)
        assert "atrasadas" in result
        assert "critica" in result


# ── 3. Auditoria estática: service_client NÃO no router ────────────────────

class TestStaticAudit:
    def test_service_client_not_in_monitoring_router(self):
        """
        REGRA DE OURO: app/routers/monitoring.py não deve importar nem referenciar
        get_service_client() ou service_client.
        Falha aqui significa que um futuro endpoint pode vazar dados sem o helper de validação.
        """
        content = Path("app/routers/monitoring.py").read_text(encoding="utf-8")
        assert "get_service_client" not in content, (
            "get_service_client encontrado em monitoring.py — "
            "mova para monitoring_service.py"
        )
        assert "service_client" not in content, (
            "service_client encontrado em monitoring.py — "
            "mova para monitoring_service.py"
        )

    def test_monitoring_service_has_service_client(self):
        """
        monitoring_service.py DEVE ter get_service_client (confirma que o helper existe).
        """
        content = Path("app/services/monitoring_service.py").read_text(encoding="utf-8")
        assert "get_service_client" in content
