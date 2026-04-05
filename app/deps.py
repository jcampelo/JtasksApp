"""
Dependências de autenticação para FastAPI

Fornece a função get_current_user() que valida a sessão do usuário
e renova o token JWT automaticamente.
"""

from datetime import datetime, timezone

from fastapi import Request
from fastapi.responses import RedirectResponse
from supabase import create_client

from app.config import settings


def get_current_user(request: Request):
    """
    Dependency de autenticação — validar sessão do usuário.

    Fluxo:
      1. Lê dados do usuário do cookie de sessão (request.session["user"])
      2. Se não existir → redireciona para /auth/login
      3. Valida se o access_token está expirado
      4. Se falta menos de 60 segundos para expirar → renova automaticamente
      5. Se renovação falhar → limpa sessão e redireciona para login

    Uso em endpoints:
      async def meu_endpoint(request: Request, user=Depends(get_current_user)):
          if isinstance(user, RedirectResponse): return user
          # user["user_id"], user["access_token"], user["refresh_token"], user["email"]

    Returns:
      dict: {
          "user_id": str (UUID do Supabase Auth),
          "email": str,
          "access_token": str (JWT válido),
          "refresh_token": str,
          "expires_at": int (timestamp Unix)
      }
      OU RedirectResponse: redireciona para /auth/login se não autenticado
    """

    # Tenta ler dados da sessão armazenados no cookie do navegador
    session = request.session.get("user")
    if not session:
        # Usuário não autenticado → redireciona para login
        return RedirectResponse(url="/auth/login", status_code=302)

    # ===== RENOVAÇÃO AUTOMÁTICA DE TOKEN =====
    # Pega timestamp de expiração do token (em segundos desde 1970)
    expires_at = session.get("expires_at", 0)

    # Calcula tempo atual em UTC
    now_ts = datetime.now(timezone.utc).timestamp()

    # Se token expira em menos de 60 segundos, renova AGORA
    # Isso evita que o token expire durante a execução do endpoint
    if now_ts >= expires_at - 60:
        try:
            # Cria cliente Supabase para renovar o token
            client = create_client(settings.supabase_url, settings.supabase_anon_key)

            # Supabase usa refresh_token para gerar novo access_token
            result = client.auth.refresh_session(session["refresh_token"])

            # Atualiza tokens na sessão (válidos por +3600 segundos)
            session["access_token"] = result.session.access_token
            session["refresh_token"] = result.session.refresh_token
            session["expires_at"] = result.session.expires_at

            # Persiste na sessão do navegador
            request.session["user"] = session

        except Exception:
            # Se renovação falhar (refresh_token expirou, etc)
            # → limpa sessão e força novo login
            request.session.clear()
            return RedirectResponse(url="/auth/login", status_code=302)

    # Token válido e renovado → retorna dados do usuário
    return session
