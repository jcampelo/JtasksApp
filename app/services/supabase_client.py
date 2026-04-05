from supabase import create_client, Client
from app.config import settings


def get_service_client() -> Client:
    """Cliente com service_role key — bypassa RLS. Usar apenas no scheduler/email."""
    return create_client(settings.supabase_url, settings.supabase_service_key)


def get_user_client(access_token: str, refresh_token: str) -> Client:
    """Cliente autenticado com o JWT do usuário — respeita RLS."""
    client = create_client(settings.supabase_url, settings.supabase_anon_key)

    # set_session() calls get_user() or _refresh_access_token() internally
    # and fires TOKEN_REFRESHED which *should* update options.headers.
    # However, if set_session() fails (network error, expired token, etc.)
    # the Authorization header silently stays as the anon key, bypassing RLS.
    #
    # To be safe, we also explicitly set the header after the call.
    # If set_session() succeeded and refreshed the token, we use the new one;
    # otherwise we fall back to the original access_token.
    try:
        res = client.auth.set_session(access_token, refresh_token)
        token = res.session.access_token if res.session else access_token
    except Exception:
        token = access_token

    client.options.headers["Authorization"] = f"Bearer {token}"
    # Reset cached sub-clients so they pick up the new Authorization header
    client._postgrest = None
    client._storage = None
    client._functions = None
    return client
