from supabase import create_client, Client
from app.config import settings


def get_service_client() -> Client:
    """Cliente com service_role key — bypassa RLS. Usar apenas no scheduler/email."""
    return create_client(settings.supabase_url, settings.supabase_service_key)


def get_user_client(access_token: str, refresh_token: str) -> Client:
    """Cliente autenticado com o JWT do usuário — respeita RLS."""
    client = create_client(settings.supabase_url, settings.supabase_anon_key)
    client.auth.set_session(access_token, refresh_token)
    return client
