-- migrations/2026-04-15_watched_users.sql
-- Tabela de usuários monitorados pelo owner.
-- Additive only — zero impacto nas tabelas existentes.

create table public.watched_users (
  id               uuid        primary key default gen_random_uuid(),
  owner_id         uuid        not null references auth.users(id) on delete cascade,
  watched_user_id  uuid        not null references auth.users(id) on delete cascade,
  pinned_at        timestamptz not null default now(),
  unique (owner_id, watched_user_id)
);

create index idx_watched_users_owner on public.watched_users(owner_id);

-- RLS: somente o owner pode ler/inserir/deletar
alter table public.watched_users enable row level security;

create policy "owner_only_select" on public.watched_users
  for select using (
    (auth.jwt() ->> 'email') = 'campelo.jefferson@gmail.com'
  );

create policy "owner_only_insert" on public.watched_users
  for insert with check (
    (auth.jwt() ->> 'email') = 'campelo.jefferson@gmail.com'
    and owner_id = auth.uid()
  );

create policy "owner_only_delete" on public.watched_users
  for delete using (
    (auth.jwt() ->> 'email') = 'campelo.jefferson@gmail.com'
    and owner_id = auth.uid()
  );
