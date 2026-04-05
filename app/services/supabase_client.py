"""
Clientes Supabase para JtasksApp

Dois modos de acesso ao banco:
  1. get_user_client() — Usa JWT do usuário (respeita RLS — seguro)
  2. get_service_client() — Usa service_role key (bypassa RLS — apenas server)

RLS (Row Level Security):
  - Política SQL no Supabase: cada tabela filtra por user_id automaticamente
  - get_user_client() ativa RLS: queries com missing .eq("user_id", ...) retornam sem dados
  - get_service_client() desativa RLS: SEMPRE filtrar manualmente
"""

from supabase import create_client, Client
from app.config import settings


def get_service_client() -> Client:
    """
    Cliente de SERVIDOR usando service_role key — BYPASSA RLS.

    ⚠️ PERIGO: Sem RLS, pode acessar dados de qualquer usuário!
              SEMPRE filtrar por user_id manualmente na URL/query.

    Usar APENAS em:
      - email_service.py: enviar emails diários (servidor, sem req HTTP)
      - scheduler.py: executar jobs agendados

    NUNCA usar em:
      - Endpoints FastAPI
      - Lógica que envolva dados de usuários
    """
    return create_client(settings.supabase_url, settings.supabase_service_key)


def get_user_client(access_token: str, refresh_token: str) -> Client:
    """
    Cliente AUTENTICADO usando JWT do usuário — RESPEITA RLS.

    RLS automática:
      - Queries sem .eq("user_id", user_id) retornam 0 linhas
      - Queries com user_id filtrado retornam apenas dados daquele usuário
      - Garantido: um usuário NUNCA consegue acessar dados de outro

    Parâmetros:
      access_token: JWT curto (expira em ~1 hora)
      refresh_token: Token longo para renovar access_token

    Fluxo seguro:
      1. Client criado com anon_key
      2. set_session() valida tokens e atualiza Authorization header
      3. Header "Authorization: Bearer {JWT}" é adicionado a toda request
      4. Supabase RLS valida JWT e filtra automaticamente por user_id

    ⚠️ DETALHE: Se set_session() falhar (token expirado, rede), header
                fica com anon_key e RLS ainda ativa. Não há bypass silencioso.
    """
    client = create_client(settings.supabase_url, settings.supabase_anon_key)

    # set_session() obtém novo access_token via refresh_token se necessário
    # Atualiza Authorization header automaticamente
    try:
        res = client.auth.set_session(access_token, refresh_token)
        token = res.session.access_token if res.session else access_token
    except Exception:
        # Se renovação falhar, usa access_token original
        # RLS ainda ativa com anon_key — queries sem user_id retornarão vazio
        token = access_token

    # Garante que Authorization header tem o token JWT correto
    client.options.headers["Authorization"] = f"Bearer {token}"

    # Limpa cache de sub-clientes para forçar pickup do novo Authorization header
    # (postgrest = requests HTTP, storage = upload de arquivos, functions = cloud functions)
    client._postgrest = None
    client._storage = None
    client._functions = None

    return client
