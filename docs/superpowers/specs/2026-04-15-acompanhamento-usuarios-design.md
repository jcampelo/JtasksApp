# Design — Acompanhamento de Usuários (Owner)

**Data:** 2026-04-15
**Autor:** Jefferson Campelo (com Claude)
**Status:** Design aprovado, aguardando plano de implementação

---

## Contexto

JtasksApp é multi-tenant: cada usuário só enxerga seus próprios dados (REGRA #1 do CLAUDE.md). O owner (`campelo.jefferson@gmail.com`) precisa de uma tela para acompanhar atividades de outros usuários — começando por **visualização read-only**, com evolução futura para interação/gerenciamento (fase C).

### Motivação de segurança

Já houve um incidente em que um novo usuário conseguiu ver dados de performance de outro usuário por falta de filtro `user_id`. Este design é construído em torno de **evitar a recorrência desse tipo de bug** via múltiplas camadas de defesa.

---

## Escopo

### Dentro
- Aba "Acompanhamento" visível **apenas** ao owner
- Owner pina/despina usuários para observar
- Cards colapsados por usuário pinado com contadores (ativas / atrasadas / concluídas hoje)
- Expansão do card mostra tarefas agrupadas (Atrasadas → Crítica → Urgente → Normal), cada grupo por `deadline ASC`
- Polling automático 30s (toggleável) + botão refresh manual que reseta o timer
- Indicador "Atualizado há Xs"

### Fora (fases futuras)
- Editar/criar/deletar tarefas de terceiros
- Performance/gráficos dos monitorados
- Notificações/alertas
- Audit log de visualizações

---

## Arquitetura

### Arquivos novos

```
app/
├── routers/
│   └── monitoring.py                    # Endpoints /monitoring/*
├── services/
│   └── monitoring_service.py            # Helper fetch_watched_user_data + validações
└── templates/partials/monitoring/
    ├── monitoring_tab.html              # Shell da aba
    ├── user_card.html                   # Card colapsado
    ├── user_card_body.html              # Corpo expandido
    └── pin_picker.html                  # Modal pinar

migrations/
└── 2026-04-15_watched_users.sql         # DDL + RLS
```

### Integração com app existente

- Novo painel `#panel-monitoring` em `pages/app.html`, condicional a `is_owner`
- Entrada "Acompanhamento" no dropdown do topbar (mesmo padrão do botão Admin)
- Reusa tokens do JEMS Design System — sem CSS novo
- Scheduler não afetado (feature síncrona, read-only)

### Fluxo

```
Owner browser
  │ HTMX GET /monitoring
  ▼
monitoring.py  ── require_owner (router-level dep)
  │
  ▼
monitoring_service.py
  │ 1. Lê watched_users do owner (user_client, RLS protege)
  │ 2. Valida watched_id ∈ watched_users
  │ 3. Busca tasks via service_client com user_id=eq.{watched_id}
  ▼
Supabase
  │ RLS em watched_users
  │ tasks via service_key (confinado ao helper)
  ▼
Templates partials/monitoring/* → HTMX swap
```

---

## Travas de Segurança (4 camadas)

1. **Gate no router inteiro**
   `APIRouter(prefix="/monitoring", dependencies=[Depends(require_owner)])`
   Novos endpoints herdam o gate automaticamente. Não há como esquecer.

2. **Helper central obrigatório**
   `fetch_watched_user_data(owner_id, watched_id, resource, user_client)`
   - Valida `watched_id ∈ watched_users[owner_id]` (404 caso não)
   - **Único** lugar que chama `get_service_client()`
   - **Sempre** injeta `.eq("user_id", watched_id)`

3. **RLS na tabela `watched_users`**
   Policies exigem `auth.jwt() ->> 'email' = 'campelo.jefferson@gmail.com'`. Se o gate do router falhar, o banco nega.

4. **Testes de regressão no CI**
   - Non-owner em todos endpoints → 403
   - Helper rejeita watched_id não pinado → 404
   - Auditoria estática: `service_client` NÃO pode aparecer em `app/routers/monitoring.py`

---

## Dados

### Tabela `watched_users`

```sql
create table public.watched_users (
  id uuid primary key default gen_random_uuid(),
  owner_id uuid not null references auth.users(id) on delete cascade,
  watched_user_id uuid not null references auth.users(id) on delete cascade,
  pinned_at timestamptz not null default now(),
  unique (owner_id, watched_user_id)
);

create index idx_watched_users_owner on public.watched_users(owner_id);
```

### RLS

```sql
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
```

### Leitura de dados

- `watched_users` → `get_user_client()` (RLS protege)
- `tasks` dos monitorados → `get_service_client()` **apenas dentro de `monitoring_service.py`**, sempre com `user_id=eq.{watched_id}`
- Lista de usuários disponíveis para pinar → consultar a mesma origem já usada pelo admin de aprovação (a confirmar na implementação)

### Migration

- Arquivo: `migrations/2026-04-15_watched_users.sql`
- Aplicada manualmente no SQL Editor do Supabase (projeto não tem banco local)

---

## Endpoints

Todos sob `APIRouter(prefix="/monitoring", dependencies=[Depends(require_owner)])`.

| Método | Path | Propósito | Retorno |
|---|---|---|---|
| GET | `/monitoring` | Carrega a aba (cards colapsados) | `monitoring_tab.html` |
| GET | `/monitoring/card/{watched_id}` | Corpo expandido (tarefas agrupadas) | `user_card_body.html` |
| GET | `/monitoring/card/{watched_id}/summary` | Só cabeçalho (polling) | `user_card.html` parcial |
| GET | `/monitoring/pin-picker` | Modal de pinar | `pin_picker.html` |
| POST | `/monitoring/pin` | Pina um usuário | HX-Trigger refresh + toast |
| DELETE | `/monitoring/pin/{watched_id}` | Despina | HX-Trigger refresh + toast |
| GET | `/monitoring/refresh-all` | Refresh manual (cabeçalhos de todos) | Lista de `user_card.html` |

### Contrato do helper

```python
# app/services/monitoring_service.py
def fetch_watched_user_data(
    owner_id: str,
    watched_id: str,
    resource: Literal["tasks_summary", "tasks_full"],
    user_client,
) -> dict | list:
    # 1. Valida watched_id ∈ watched_users[owner_id] (user_client)
    #    Se não → HTTPException(404)
    # 2. Abre service_client
    # 3. Query SEMPRE com .eq("user_id", watched_id)
    # 4. Retorna dados processados
```

Regra de ouro: `grep service_client app/routers/monitoring.py` deve retornar zero.

---

## UI/UX

### Layout da aba

```
┌─ Acompanhamento ────────────────────────────────────────┐
│  [🔄 Atualizar]  [⏱ Auto 30s: ●ON]   Atualizado há 12s │
│                                              [+ Pinar]  │
├─────────────────────────────────────────────────────────┤
│  ▶ João Silva     3 ativas · 1 atrasada · 2 hoje    📌 │
│  ▶ Maria Costa    7 ativas · 0 atrasada · 0 hoje    📌 │
│  ▼ Pedro Lima     5 ativas · 2 atrasadas · 1 hoje   📌 │
│    ─ Atrasadas ────────────────────────────────────    │
│    🔴 Deploy VPS       Infra    14/04 (2d atrás)       │
│    🟠 Revisar PR       Backend  13/04 (3d atrás)       │
│    ─ Crítica ──────────────────────────────────────    │
│    🔴 Hotfix login     Auth     16/04                  │
│    ─ Urgente ──────────────────────────────────────    │
│    🟠 Review specs     Docs     17/04                  │
│    ─ Normal ───────────────────────────────────────    │
│    ⚪ Organizar wiki   Docs     22/04                  │
└─────────────────────────────────────────────────────────┘
```

### Card colapsado

- Chevron (▶/▼) + nome
- Contadores: `N ativas · N atrasada(s) · N concluídas hoje`
  - "atrasada" em vermelho se > 0
  - "hoje" em verde
- 📌 à direita (tooltip "Despinar", clique confirma)
- Clique no cabeçalho expande via HTMX (lazy — só busca ao expandir)

### Card expandido

Grupos fixos, ordem:
1. Atrasadas (deadline < hoje, status=active)
2. Crítica (não atrasadas)
3. Urgente
4. Normal

Dentro de cada grupo: `deadline ASC`. Grupos vazios não renderizam.

Linha: `[ícone prioridade] Nome   Projeto   Deadline (Xd)`. Read-only nesta fase.

### Modal "Pinar usuários"

- Lista todos os usuários (exceto owner)
- Linha: nome + email + botão `[+ Pinar]` ou `[✓ Pinado]`
- Busca client-side (Alpine)
- Fecha com Esc ou clique fora

### Estados vazios

- Sem pinados: "Nenhum usuário pinado. Clique em **+ Pinar** para começar."
- Card sem ativas: "Sem tarefas ativas 🎉"

### Polling/refresh

- Toggle Alpine: `setInterval(30_000)` → `GET /monitoring/refresh-all`
- Botão refresh: chama o mesmo endpoint + `clearInterval` + `setInterval` (reseta timer)
- "Atualizado há Xs" calculado client-side a partir do último swap

### Acessibilidade

- `aria-expanded` nos chevrons
- `aria-label` nos botões de pin/despin

---

## Testes

### 1. Regressão de segurança (CI)

```python
# tests/test_monitoring_security.py
def test_non_owner_gets_403_on_all_endpoints(client, regular_user_session):
    for method, path in [
        ("GET", "/monitoring"),
        ("GET", f"/monitoring/card/{any_uuid}"),
        ("GET", f"/monitoring/card/{any_uuid}/summary"),
        ("GET", "/monitoring/pin-picker"),
        ("POST", "/monitoring/pin"),
        ("DELETE", f"/monitoring/pin/{any_uuid}"),
        ("GET", "/monitoring/refresh-all"),
    ]:
        resp = client.request(method, path)
        assert resp.status_code == 403
```

### 2. Validação de pin

```python
def test_fetch_rejects_non_pinned_user():
    with pytest.raises(HTTPException) as exc:
        fetch_watched_user_data(owner_id, random_uuid, "tasks_full", client)
    assert exc.value.status_code == 404
```

### 3. Auditoria estática

```python
def test_service_client_only_in_monitoring_service():
    content = Path("app/routers/monitoring.py").read_text()
    assert "get_service_client" not in content
    assert "service_client" not in content
```

### 4. Smoke funcional

- Pinar → usuário aparece
- Expandir → tarefas do usuário correto
- Despinar → usuário some

---

## Riscos

| Risco | Mitigação |
|---|---|
| Vazamento de dados (bug histórico) | 4 travas: gate + helper + RLS + testes |
| Carga de polling | `refresh-all` devolve só cabeçalhos; query agregada `user_id IN (...)` |
| N+1 de queries | Query única no helper agregador, processa em Python |
| Owner muda email | `OWNER_EMAIL` constante + RLS precisam ser atualizados juntos — documentar |
| Usuário deletado com pin ativo | `ON DELETE CASCADE` resolve |
| Scroll com muitos pinados | Fora de escopo; cards colapsados mantêm a tela leve |
| Fase C quebra isolamento | Todas as mutations futuras via `monitoring_service.py` — herdam travas |

---

## Critérios de Aceitação

- Owner vê aba "Acompanhamento"; outros usuários **não**
- Owner pina/despina via modal
- Cards colapsados por padrão; expandem on-demand
- Tarefas agrupadas: Atrasadas → Crítica → Urgente → Normal, cada grupo por `deadline ASC`
- Polling 30s + refresh manual que reseta timer
- Indicador "Atualizado há Xs" atualiza a cada swap
- Todos os testes de segurança passam no CI
- `grep service_client app/routers/monitoring.py` → zero resultados
