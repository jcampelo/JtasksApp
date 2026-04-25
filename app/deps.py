from datetime import datetime, timezone

from fastapi import Depends, HTTPException, Request
from fastapi.responses import RedirectResponse
from supabase import create_client

from app.config import settings
from app.services.approval_service import OWNER_EMAIL
from app.services.permissions_service import has_feature
from app.services import session_service


def get_current_user(request: Request):
    """
    Dependency que resolve session_id do cookie, busca sessão server-side,
    renova token se necessário. Redireciona para /auth/login se não autenticado.
    """
    session_id = request.session.get("session_id")
    if not session_id:
        return RedirectResponse(url="/auth/login", status_code=302)

    session = session_service.get_session(session_id)
    if not session:
        request.session.clear()
        return RedirectResponse(url="/auth/login", status_code=302)

    # Renovar token se estiver perto de expirar
    expires_at = session.get("expires_at", 0)
    now_ts = datetime.now(timezone.utc).timestamp()

    if now_ts >= expires_at - 60:
        try:
            client = create_client(settings.supabase_url, settings.supabase_anon_key)
            result = client.auth.refresh_session(session["refresh_token"])
            session_service.update_tokens(
                session_id=session_id,
                access_token=result.session.access_token,
                refresh_token=result.session.refresh_token,
                expires_at=result.session.expires_at,
            )
            session["access_token"] = result.session.access_token
            session["refresh_token"] = result.session.refresh_token
            session["expires_at"] = result.session.expires_at
        except Exception:
            session_service.delete_session(session_id)
            request.session.clear()
            return RedirectResponse(url="/auth/login", status_code=302)

    return session


def require_owner(user=Depends(get_current_user)):
    """
    Gate exclusivo para administração de permissões (painel master).
    Para gates de produto, usar require_feature(name).
    """
    if isinstance(user, RedirectResponse):
        raise HTTPException(status_code=403, detail="Não autenticado.")
    if user.get("email") != OWNER_EMAIL:
        raise HTTPException(status_code=403, detail="Acesso negado.")
    return user


def require_feature(feature: str):
    """
    Factory que retorna dependency validando acesso à feature pelo usuário.
    Owner sempre passa (recebe KNOWN_FEATURES implicitamente).
    """
    def _check(request: Request, user=Depends(get_current_user)):
        if isinstance(user, RedirectResponse):
            raise HTTPException(status_code=403, detail="Não autenticado.")
        if not has_feature(user, request, feature):
            raise HTTPException(status_code=403, detail="Acesso negado.")
        return user

    return _check
