-- =============================================================
-- Jtasks — Supabase Setup
-- Execute este arquivo no SQL Editor do Supabase:
-- painel.supabase.com → seu projeto → SQL Editor → New query
-- =============================================================


-- -------------------------------------------------------------
-- 1. TABELAS
-- -------------------------------------------------------------

-- Projetos (por usuário)
CREATE TABLE projects (
  id         UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id    UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
  name       TEXT NOT NULL,
  created_at TIMESTAMPTZ DEFAULT NOW(),
  UNIQUE(user_id, name)
);

-- Presets / atividades recorrentes (por usuário)
CREATE TABLE presets (
  id         UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id    UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
  name       TEXT NOT NULL,
  project    TEXT,
  priority   TEXT CHECK (priority IN ('critica','urgente','normal')) DEFAULT 'normal',
  created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Tarefas (por usuário)
CREATE TABLE tasks (
  id           UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id      UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
  name         TEXT NOT NULL,
  project      TEXT,
  priority     TEXT CHECK (priority IN ('critica','urgente','normal')) DEFAULT 'normal',
  date         DATE NOT NULL DEFAULT CURRENT_DATE,
  deadline     DATE,
  created_at   TIMESTAMPTZ DEFAULT NOW(),
  completed_at TIMESTAMPTZ,
  status       TEXT CHECK (status IN ('active','completed','discarded')) DEFAULT 'active'
);

-- Atualizações de tarefas
CREATE TABLE task_updates (
  id         UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  task_id    UUID NOT NULL REFERENCES tasks(id) ON DELETE CASCADE,
  user_id    UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
  text       TEXT NOT NULL,
  created_at TIMESTAMPTZ DEFAULT NOW()
);


-- -------------------------------------------------------------
-- 2. ROW LEVEL SECURITY (RLS)
-- Garante que cada usuário veja e altere apenas seus próprios dados
-- -------------------------------------------------------------

ALTER TABLE tasks        ENABLE ROW LEVEL SECURITY;
ALTER TABLE projects     ENABLE ROW LEVEL SECURITY;
ALTER TABLE presets      ENABLE ROW LEVEL SECURITY;
ALTER TABLE task_updates ENABLE ROW LEVEL SECURITY;

CREATE POLICY "own_tasks"    ON tasks        FOR ALL USING (auth.uid() = user_id);
CREATE POLICY "own_projects" ON projects     FOR ALL USING (auth.uid() = user_id);
CREATE POLICY "own_presets"  ON presets      FOR ALL USING (auth.uid() = user_id);
CREATE POLICY "own_updates"  ON task_updates FOR ALL USING (auth.uid() = user_id);


-- -------------------------------------------------------------
-- 3. CONFIGURAÇÕES DE AUTENTICAÇÃO (fazer no painel, não via SQL)
-- -------------------------------------------------------------
-- Authentication → Sign In / Providers → Email:
--   ✅ Enable Email provider         → ATIVADO
--   ☐ Confirm email                  → DESATIVADO
--
-- Para criar usuários:
--   Authentication → Users → Add user → Create new user
--   Marcar "Auto Confirm User" para o usuário já poder logar imediatamente


-- -------------------------------------------------------------
-- 4. CREDENCIAIS NECESSÁRIAS NO CÓDIGO
-- -------------------------------------------------------------
-- Encontre em: Settings → API
--
-- SUPABASE_URL      → Project URL          (ex: https://xyzxyz.supabase.co)
-- SUPABASE_ANON_KEY → Project API Keys → anon / public
--                     (usado no index.html — seguro expor no frontend)
-- SUPABASE_SERVICE_KEY → Project API Keys → service_role / secret
--                     (usado no server.py — NUNCA expor no frontend)
