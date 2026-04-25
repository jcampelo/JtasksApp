-- Session store server-side para JtasksApp
-- Substitui o armazenamento de tokens no cookie Starlette
-- O navegador passa a guardar apenas session_id (UUID opaco)

CREATE TABLE IF NOT EXISTS app_sessions (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id         UUID NOT NULL,
    email           TEXT NOT NULL,
    access_token    TEXT NOT NULL,
    refresh_token   TEXT NOT NULL,
    expires_at      BIGINT NOT NULL,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    last_seen_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
    revoked_at      TIMESTAMPTZ
);

-- Índice para lookup por session_id (path quente em todo request autenticado)
CREATE INDEX IF NOT EXISTS app_sessions_id_idx ON app_sessions (id);

-- Índice para revogar todas as sessões de um usuário
CREATE INDEX IF NOT EXISTS app_sessions_user_id_idx ON app_sessions (user_id);

-- RLS: apenas o service_role pode ler/escrever (o app usa service_key para sessões)
ALTER TABLE app_sessions ENABLE ROW LEVEL SECURITY;

-- Nenhuma policy de usuário — acesso exclusivo via service_role
-- (o app nunca usa anon_key para tocar nessa tabela)
