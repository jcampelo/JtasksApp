-- Gate de aprovação para novos cadastros.
-- Rodar no SQL Editor do Supabase.

create table if not exists public.user_approvals (
  user_id      uuid primary key references auth.users(id) on delete cascade,
  email        text not null,
  status       text not null default 'pending' check (status in ('pending','approved','rejected')),
  requested_at timestamptz not null default now(),
  approved_at  timestamptz,
  approved_by  uuid references auth.users(id)
);

create index if not exists user_approvals_status_idx on public.user_approvals(status);

alter table public.user_approvals enable row level security;

-- Somente service_role lê/escreve. Endpoints do backend usam service client com
-- filtro explícito. Nenhuma policy para authenticated — o backend é a autoridade.
drop policy if exists "service_role full access" on public.user_approvals;
create policy "service_role full access"
  on public.user_approvals
  as permissive
  for all
  to service_role
  using (true)
  with check (true);

-- Bootstrap: aprovar o dono.
insert into public.user_approvals (user_id, email, status, approved_at)
select id, email, 'approved', now()
from auth.users
where email = 'campelo.jefferson@gmail.com'
on conflict (user_id) do update
  set status = 'approved', approved_at = now();
