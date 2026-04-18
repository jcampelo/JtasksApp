-- migrations/2026-04-16_user_features.sql
-- Tabela genérica de feature flags por usuário.
-- Master (OWNER_EMAIL) concede/revoga via service_key (bypassa RLS).
-- Additive only — zero impacto nas tabelas existentes.

create table public.user_features (
    user_id     uuid        not null references auth.users(id) on delete cascade,
    feature     text        not null,
    enabled_at  timestamptz not null default now(),
    primary key (user_id, feature)
);

create index user_features_feature_idx on public.user_features(feature);

-- RLS: cada usuário lê APENAS suas próprias features.
-- INSERT/UPDATE/DELETE bloqueados pra todos (service_key bypassa).
alter table public.user_features enable row level security;

create policy user_features_select_own on public.user_features
    for select using (auth.uid() = user_id);
