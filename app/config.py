"""
Configurações da aplicação JtasksApp

Carrega variáveis de ambiente do arquivo .env usando Pydantic Settings.
Essas variáveis são críticas para o funcionamento da aplicação.
"""

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """
    Classe que carrega e valida todas as variáveis de ambiente.

    Pydantic valida os tipos e garante que variáveis obrigatórias existem.
    Se uma variável obrigatória não estiver em .env, a app falha na inicialização.
    """

    # Configuração: ler do arquivo .env na raiz do projeto
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    # ===== SUPABASE (Backend Database) =====
    # supabase_url: URL do projeto Supabase (ex: https://xxx.supabase.co)
    supabase_url: str

    # supabase_anon_key: Chave anônima para requisições do navegador/app
    # Usa RLS (Row Level Security) — cada usuário vê apenas seus dados
    supabase_anon_key: str

    # supabase_service_key: Chave de serviço (BYPASSA RLS)
    # Usar APENAS em server-side (email_service.py)
    # ⚠️ NUNCA expor ao frontend
    supabase_service_key: str

    # ===== SEGURANÇA =====
    # secret_key: Chave secreta para SessionMiddleware (criptografia de sessão)
    # DEVE ser forte, única, e NUNCA fazer commit no git
    secret_key: str

    # port: Porta onde FastAPI roda (padrão: 8080)
    port: int = 8080

    # ===== SMTP (Email) =====
    # smtp_host: Servidor de email (Zoho Mail)
    smtp_host: str = "smtp.zoho.com"

    # smtp_port: Porta SMTP (465 = SSL, 587 = TLS)
    smtp_port: int = 465

    # smtp_user: Email remetente (ex: noreply@company.com)
    smtp_user: str = ""

    # smtp_password: Senha da conta de email
    # ⚠️ NUNCA fazer commit no git
    smtp_password: str = ""

    # smtp_from_name: Nome exibido no "De:" dos emails
    smtp_from_name: str = "Jtasks"


# Instancia global de settings
# Usada em toda a aplicação para acessar configurações: settings.supabase_url, etc
settings = Settings()
