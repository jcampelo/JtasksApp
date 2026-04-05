from datetime import datetime, timezone

from fastapi import Request
from fastapi.responses import RedirectResponse
from supabase import create_client

from app.config import settings


def get_current_user(request: Request):
    """
    Dependency que lê a sessão do cookie, verifica expiração e renova se necessário.
    Redireciona para /auth/login se não autenticado.
    """
    session = request.session.get("user")
    if not session:
        return RedirectResponse(url="/auth/login", status_code=302)

    # Verificar expiração do token
    expires_at = session.get("expires_at", 0)
    now_ts = datetime.now(timezone.utc).timestamp()

    if now_ts >= expires_at - 60:  # renovar 60s antes de expirar
        try:
            client = create_client(settings.supabase_url, settings.supabase_anon_key)
            result = client.auth.refresh_session(session["refresh_token"])
            session["access_token"] = result.session.access_token
            session["refresh_token"] = result.session.refresh_token
            session["expires_at"] = result.session.expires_at
            request.session["user"] = session
        except Exception:
            request.session.clear()
            return RedirectResponse(url="/auth/login", status_code=302)

    return session
