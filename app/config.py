from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    supabase_url: str
    supabase_anon_key: str
    supabase_service_key: str
    secret_key: str
    port: int = 8080

    # SMTP — Zoho Mail (configurado na VPS, não exposto ao usuário)
    smtp_host: str = "smtp.zoho.com"
    smtp_port: int = 465
    smtp_user: str = ""
    smtp_password: str = ""
    smtp_from_name: str = "Jtasks"

    # Telegram Bot
    telegram_bot_token: str = ""
    groq_api_key: str = ""
    bot_api_key: str = ""
    bot_owner_user_id: str = ""
    jtasks_internal_url: str = "http://localhost:8000"


settings = Settings()
