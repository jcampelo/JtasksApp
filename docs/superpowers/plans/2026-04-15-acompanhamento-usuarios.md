# Acompanhamento de Usuários — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Adicionar aba "Acompanhamento" exclusiva ao owner para monitorar tarefas de outros usuários de forma read-only, com segurança em 4 camadas para evitar vazamento de dados entre usuários.

**Architecture:** Router `/monitoring` com gate `require_owner` aplicado em nível de router (todos os endpoints herdam automaticamente). `monitoring_service.py` é o único arquivo que acessa `get_service_client()` — sempre valida o pin antes da query e sempre injeta `.eq("user_id", watched_id)`. RLS no banco é a camada de defesa final.

**Tech Stack:** FastAPI + HTMX + Alpine.js + Jinja2 + Supabase Python SDK + pytest

---

## Mapa de Arquivos

| Ação | Arquivo | Responsabilidade |
|------|---------|-----------------|
| Criar | `migrations/2026-04-15_watched_users.sql` | DDL + RLS da tabela `watched_users` |
| Modificar | `app/deps.py` | Adicionar dependency `require_owner` |
| Criar | `app/services/monitoring_service.py` | Toda lógica de negócio + único acesso ao `service_client` |
| Criar | `app/routers/monitoring.py` | 7 endpoints, gate em nível de router |
| Criar | `app/templates/partials/monitoring/monitoring_tab.html` | Shell da aba com Alpine polling |
| Criar | `app/templates/partials/monitoring/user_card.html` | Card colapsado + cabeçalho |
| Criar | `app/templates/partials/monitoring/user_card_body.html` | Corpo expandido com tarefas agrupadas |
| Criar | `app/templates/partials/monitoring/pin_picker.html` | Modal de pinar usuários |
| Modificar | `main.py` | Import + `include_router(monitoring.router)` |
| Modificar | `app/templates/pages/app.html` | Adicionar `#panel-monitoring` |
| Modificar | `app/templates/partials/sidebar.html` | Botão "Acompanhamento" condicional ao owner |
| Criar | `tests/__init__.py` | Pacote de testes |
| Criar | `tests/conftest.py` | Fixtures pytest (TestClient, usuários fake) |
| Criar | `tests/test_monitoring_security.py` | Regressão de segurança + auditoria estática |

---

## Task 1: Migration SQL

**Files:**
- Create: `migrations/2026-04-15_watched_users.sql`

> Não há banco local. Esta migration é executada manualmente no SQL Editor do Supabase. A task é criar o arquivo e depois aplicá-lo.

- [x] **Step 1: Criar o arquivo de migration**

```sql
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
```

- [ ] **Step 2: Aplicar no Supabase**

Abrir o SQL Editor do projeto no Supabase, colar o conteúdo do arquivo e executar. Verificar que a tabela `watched_users` aparece no Table Editor.

- [x] **Step 3: Commit** — `8d5a52b`

---

## Task 2: Dependency `require_owner`

**Files:**
- Modify: `app/deps.py`

- [x] **Step 1: Escrever o teste que vai falhar**

```python
# tests/test_require_owner.py  (arquivo temporário, integrado ao test_monitoring_security.py no Task 7)
# Por ora, apenas confirme mentalmente o contrato:
# require_owner(user=regular_user) → HTTPException(403)
# require_owner(user=owner_user)   → retorna o user dict
```

*Nota: os testes reais ficam no Task 7. Aqui só implementamos.*

- [x] **Step 2: Implementar `require_owner` em `app/deps.py`**

Adicionar ao final do arquivo existente (após a função `get_current_user`):

```python
from fastapi import Depends, HTTPException
from fastapi.responses import RedirectResponse
from app.services.approval_service import OWNER_EMAIL


def require_owner(user=Depends(get_current_user)):
    """
    FastAPI Dependency que exige que o usuário autenticado seja o owner.
    Levanta HTTPException(403) para não-owners — adequado para endpoints HTMX.
    Retorna o dict do usuário para uso nos endpoints.
    """
    if isinstance(user, RedirectResponse):
        raise HTTPException(status_code=403, detail="Não autenticado.")
    if user.get("email") != OWNER_EMAIL:
        raise HTTPException(status_code=403, detail="Acesso negado.")
    return user
```

- [x] **Step 3: Verificar que `app/deps.py` não quebra imports existentes**

```bash
cd c:/Users/campe/projetos-claude-code/JtasksApp
.venv/Scripts/python -c "from app.deps import get_current_user, require_owner; print('OK')"
```

Esperado: `OK`

- [x] **Step 4: Commit** — `9fb985f`

---

## Task 3: `monitoring_service.py`

**Files:**
- Create: `app/services/monitoring_service.py`

Este arquivo é o **único** que pode chamar `get_service_client()` no contexto de monitoring.

- [ ] **Step 1: Criar o arquivo**

```python
# app/services/monitoring_service.py
"""
Serviço de monitoramento de usuários (owner only).

REGRA DE OURO: get_service_client() é chamado APENAS aqui.
Toda query às tasks de outros usuários SEMPRE usa .eq("user_id", watched_user_id).
"""
from datetime import date, timezone, datetime
from typing import Literal

from fastapi import HTTPException

from app.services.supabase_client import get_service_client
from app.services.approval_service import list_all as list_all_approvals, OWNER_EMAIL


def get_watched_users(owner_id: str, user_client) -> list[dict]:
    """Retorna lista de watched_users do owner (via user_client com RLS)."""
    res = (
        user_client.table("watched_users")
        .select("watched_user_id, pinned_at")
        .eq("owner_id", owner_id)
        .order("pinned_at")
        .execute()
    )
    return res.data or []


def get_all_summaries(owner_id: str, user_client) -> list[dict]:
    """
    Busca todos os usuários pinados e seus resumos em queries batch (não N+1).
    Retorna lista de dicts com: watched_user_id, email, active, overdue, completed_today.
    """
    watched = get_watched_users(owner_id, user_client)
    if not watched:
        return []

    watched_ids = [w["watched_user_id"] for w in watched]
    today = date.today().isoformat()
    today_start = today + "T00:00:00"

    svc = get_service_client()

    # Email dos usuários monitorados (via user_approvals)
    emails_res = (
        svc.table("user_approvals")
        .select("user_id, email")
        .in_("user_id", watched_ids)
        .execute()
    )
    email_map = {e["user_id"]: e["email"] for e in (emails_res.data or [])}

    # Tarefas ativas de todos os monitorados — query batch
    active_res = (
        svc.table("tasks")
        .select("id, user_id, deadline")
        .in_("user_id", watched_ids)
        .eq("status", "active")
        .execute()
    )

    # Concluídas hoje de todos os monitorados — query batch
    completed_res = (
        svc.table("tasks")
        .select("id, user_id")
        .in_("user_id", watched_ids)
        .eq("status", "completed")
        .gte("completed_at", today_start)
        .execute()
    )

    # Agrupa em Python
    active_by_user: dict[str, list] = {}
    for t in (active_res.data or []):
        active_by_user.setdefault(t["user_id"], []).append(t)

    completed_by_user: dict[str, list] = {}
    for t in (completed_res.data or []):
        completed_by_user.setdefault(t["user_id"], []).append(t)

    result = []
    for wid in watched_ids:
        active = active_by_user.get(wid, [])
        completed = completed_by_user.get(wid, [])
        overdue = sum(
            1 for t in active
            if t.get("deadline") and t["deadline"] < today
        )
        result.append({
            "watched_user_id": wid,
            "email": email_map.get(wid, wid),
            "active": len(active),
            "overdue": overdue,
            "completed_today": len(completed),
        })

    return result


def _group_tasks(tasks: list[dict]) -> dict:
    """Agrupa tarefas ativas por prioridade/atraso, cada grupo ordenado por deadline ASC."""
    today = date.today().isoformat()
    atrasadas, critica, urgente, normal = [], [], [], []

    for t in tasks:
        deadline = t.get("deadline") or ""
        if deadline and deadline < today:
            atrasadas.append(t)
        elif t.get("priority") == "critica":
            critica.append(t)
        elif t.get("priority") == "urgente":
            urgente.append(t)
        else:
            normal.append(t)

    sort_key = lambda t: t.get("deadline") or "9999-12-31"
    for grp in [atrasadas, critica, urgente, normal]:
        grp.sort(key=sort_key)

    return {
        "atrasadas": atrasadas,
        "critica": critica,
        "urgente": urgente,
        "normal": normal,
    }


def fetch_watched_user_data(
    owner_id: str,
    watched_id: str,
    resource: Literal["tasks_full"],
    user_client,
) -> dict:
    """
    ÚNICO ponto de acesso a get_service_client() para tasks de outros usuários.
    1. Valida que watched_id está nos pinados do owner (via user_client com RLS).
    2. Busca tasks via service_client SEMPRE com .eq("user_id", watched_id).
    3. Retorna dados agrupados.
    """
    # Camada de validação: watched_id deve estar nos pinados do owner
    pin_check = (
        user_client.table("watched_users")
        .select("id")
        .eq("owner_id", owner_id)
        .eq("watched_user_id", watched_id)
        .limit(1)
        .execute()
    )
    if not pin_check.data:
        raise HTTPException(status_code=404, detail="Usuário não pinado.")

    svc = get_service_client()
    tasks_res = (
        svc.table("tasks")
        .select("id, name, project, priority, deadline, status")
        .eq("user_id", watched_id)  # SEMPRE filtrado por watched_id
        .eq("status", "active")
        .execute()
    )
    return _group_tasks(tasks_res.data or [])


def get_all_users_for_picker(owner_id: str, user_client) -> list[dict]:
    """
    Retorna todos os usuários aprovados (exceto o owner) com flag 'pinned'.
    Usado no modal de pinar.
    """
    all_approvals = list_all_approvals()  # usa get_service_client() internamente
    watched = get_watched_users(owner_id, user_client)
    pinned_ids = {w["watched_user_id"] for w in watched}

    result = []
    for a in all_approvals:
        if a["email"] == OWNER_EMAIL:
            continue
        if a.get("status") != "approved":
            continue
        result.append({
            "user_id": a["user_id"],
            "email": a["email"],
            "pinned": a["user_id"] in pinned_ids,
        })
    return result


def pin_user(owner_id: str, watched_id: str, user_client) -> None:
    """Pina um usuário (insert idempotente)."""
    user_client.table("watched_users").upsert(
        {"owner_id": owner_id, "watched_user_id": watched_id},
        on_conflict="owner_id,watched_user_id",
    ).execute()


def unpin_user(owner_id: str, watched_id: str, user_client) -> None:
    """Despina um usuário."""
    user_client.table("watched_users").delete().eq("owner_id", owner_id).eq(
        "watched_user_id", watched_id
    ).execute()
```

- [ ] **Step 2: Verificar imports**

```bash
cd c:/Users/campe/projetos-claude-code/JtasksApp
.venv/Scripts/python -c "from app.services.monitoring_service import fetch_watched_user_data, get_all_summaries; print('OK')"
```

Esperado: `OK`

- [ ] **Step 3: Commit**

```bash
git add app/services/monitoring_service.py
git commit -m "feat: monitoring_service - fetch/group/pin helpers"
```

---

## Task 4: Router `monitoring.py`

**Files:**
- Create: `app/routers/monitoring.py`

**REGRA:** `grep service_client app/routers/monitoring.py` deve retornar zero resultados.

- [ ] **Step 1: Criar o router**

```python
# app/routers/monitoring.py
"""
Router de acompanhamento de usuários (owner only).

Gate de segurança aplicado em nível de router — todos os endpoints herdam.
NUNCA importar get_service_client() aqui. Toda lógica de dados fica em monitoring_service.py.
"""
import json

from fastapi import APIRouter, Request, Depends, Form
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

from app.deps import require_owner, get_current_user
from app.services.supabase_client import get_user_client
from app.services import monitoring_service

router = APIRouter(
    prefix="/monitoring",
    dependencies=[Depends(require_owner)],  # Gate aplicado em todos os endpoints
)
templates = Jinja2Templates(directory="app/templates")


def _get_client(user: dict):
    return get_user_client(user["access_token"], user["refresh_token"])


@router.get("", response_class=HTMLResponse)
async def monitoring_tab(request: Request, user=Depends(require_owner)):
    """Carrega a aba com cards colapsados (summaries de todos os pinados)."""
    client = _get_client(user)
    summaries = monitoring_service.get_all_summaries(user["user_id"], client)
    return templates.TemplateResponse(
        "partials/monitoring/monitoring_tab.html",
        {"request": request, "summaries": summaries},
    )


@router.get("/card/{watched_id}", response_class=HTMLResponse)
async def card_body(watched_id: str, request: Request, user=Depends(require_owner)):
    """Corpo expandido com tarefas agrupadas (lazy, ao expandir o card)."""
    client = _get_client(user)
    groups = monitoring_service.fetch_watched_user_data(
        user["user_id"], watched_id, "tasks_full", client
    )
    return templates.TemplateResponse(
        "partials/monitoring/user_card_body.html",
        {"request": request, "groups": groups, "watched_id": watched_id},
    )


@router.get("/refresh-all", response_class=HTMLResponse)
async def refresh_all(request: Request, user=Depends(require_owner)):
    """Refresh manual ou por polling — retorna apenas os cabeçalhos dos cards."""
    client = _get_client(user)
    summaries = monitoring_service.get_all_summaries(user["user_id"], client)
    return templates.TemplateResponse(
        "partials/monitoring/user_cards_list.html",
        {"request": request, "summaries": summaries},
    )


@router.get("/pin-picker", response_class=HTMLResponse)
async def pin_picker(request: Request, user=Depends(require_owner)):
    """Modal de pinar usuários."""
    client = _get_client(user)
    users = monitoring_service.get_all_users_for_picker(user["user_id"], client)
    return templates.TemplateResponse(
        "partials/monitoring/pin_picker.html",
        {"request": request, "users": users},
    )


@router.post("/pin", response_class=HTMLResponse)
async def pin(
    request: Request,
    watched_id: str = Form(...),
    user=Depends(require_owner),
):
    """Pina um usuário e retorna a lista atualizada de usuários no picker."""
    client = _get_client(user)
    monitoring_service.pin_user(user["user_id"], watched_id, client)
    users = monitoring_service.get_all_users_for_picker(user["user_id"], client)
    response = templates.TemplateResponse(
        "partials/monitoring/pin_picker_list.html",
        {"request": request, "users": users},
    )
    response.headers["HX-Trigger"] = json.dumps({"refreshMonitoringCards": True})
    return response


@router.delete("/pin/{watched_id}", response_class=HTMLResponse)
async def unpin(watched_id: str, request: Request, user=Depends(require_owner)):
    """Despina um usuário e retorna os cards atualizados."""
    client = _get_client(user)
    monitoring_service.unpin_user(user["user_id"], watched_id, client)
    summaries = monitoring_service.get_all_summaries(user["user_id"], client)
    response = templates.TemplateResponse(
        "partials/monitoring/user_cards_list.html",
        {"request": request, "summaries": summaries},
    )
    response.headers["HX-Trigger"] = json.dumps(
        {"showToast": "Usuário despinado."}
    )
    return response
```

- [ ] **Step 2: Verificar que service_client não aparece no router**

```bash
grep -n "service_client\|get_service_client" c:/Users/campe/projetos-claude-code/JtasksApp/app/routers/monitoring.py
```

Esperado: zero linhas de output.

- [ ] **Step 3: Verificar imports**

```bash
cd c:/Users/campe/projetos-claude-code/JtasksApp
.venv/Scripts/python -c "from app.routers.monitoring import router; print('OK')"
```

Esperado: `OK`

- [ ] **Step 4: Commit**

```bash
git add app/routers/monitoring.py
git commit -m "feat: monitoring router (7 endpoints, require_owner gate)"
```

---

## Task 5: Templates

**Files:**
- Create: `app/templates/partials/monitoring/monitoring_tab.html`
- Create: `app/templates/partials/monitoring/user_cards_list.html`
- Create: `app/templates/partials/monitoring/user_card.html`
- Create: `app/templates/partials/monitoring/user_card_body.html`
- Create: `app/templates/partials/monitoring/pin_picker.html`
- Create: `app/templates/partials/monitoring/pin_picker_list.html`

*Nota: `user_cards_list.html` e `pin_picker_list.html` são fragments auxiliares retornados pelos endpoints de refresh/pin para atualizar partes específicas da UI.*

- [ ] **Step 1: Criar `monitoring_tab.html` (shell da aba com Alpine polling)**

```html
<!-- app/templates/partials/monitoring/monitoring_tab.html -->
<div id="monitoring-panel"
     x-data="{
       autoRefresh: true,
       lastUpdated: Date.now(),
       timer: null,
       secondsAgo: 0,
       init() {
         this.startTimer();
         setInterval(() => { this.secondsAgo = Math.round((Date.now() - this.lastUpdated) / 1000); }, 1000);
         this.$watch('autoRefresh', () => this.startTimer());
       },
       startTimer() {
         clearInterval(this.timer);
         this.timer = this.autoRefresh
           ? setInterval(() => this.doRefresh(), 30000)
           : null;
       },
       doRefresh() {
         htmx.ajax('GET', '/monitoring/refresh-all', {target: '#monitoring-cards', swap: 'innerHTML'});
         this.lastUpdated = Date.now();
         this.secondsAgo = 0;
       },
       manualRefresh() {
         this.doRefresh();
         this.startTimer();
       }
     }"
     style="padding: 16px;">

  <!-- Toolbar -->
  <div style="display:flex; align-items:center; gap:12px; margin-bottom:16px; flex-wrap:wrap;">
    <button class="btn btn-secondary btn-sm" @click="manualRefresh()" title="Atualizar agora">
      ↻ Atualizar
    </button>
    <button class="btn btn-sm"
            :class="autoRefresh ? 'btn-accent' : 'btn-secondary'"
            @click="autoRefresh = !autoRefresh"
            :title="autoRefresh ? 'Desativar atualização automática' : 'Ativar atualização automática'">
      ⏱ Auto 30s: <span x-text="autoRefresh ? 'ON' : 'OFF'"></span>
    </button>
    <span style="color: var(--text-muted); font-size:0.85rem; margin-left:auto;">
      Atualizado há <span x-text="secondsAgo < 60 ? secondsAgo + 's' : Math.round(secondsAgo/60) + 'min'"></span>
    </span>
    <button class="btn btn-primary btn-sm"
            hx-get="/monitoring/pin-picker"
            hx-target="#modal-container"
            hx-swap="innerHTML">
      + Pinar
    </button>
  </div>

  <!-- Cards (ouve evento de refresh disparado por pin/unpin) -->
  <div id="monitoring-cards"
       hx-get="/monitoring/refresh-all"
       hx-trigger="refreshMonitoringCards from:body"
       hx-swap="innerHTML">
    {% include "partials/monitoring/user_cards_list.html" %}
  </div>
</div>
```

- [ ] **Step 2: Criar `user_cards_list.html` (fragment: lista de cards)**

```html
<!-- app/templates/partials/monitoring/user_cards_list.html -->
{% if summaries %}
  {% for s in summaries %}
    {% include "partials/monitoring/user_card.html" %}
  {% endfor %}
{% else %}
  <p style="color: var(--text-muted); text-align:center; padding:32px 0;">
    Nenhum usuário pinado. Clique em <strong>+ Pinar</strong> para começar.
  </p>
{% endif %}
```

- [ ] **Step 3: Criar `user_card.html` (card colapsado com Alpine lazy-load)**

```html
<!-- app/templates/partials/monitoring/user_card.html -->
<!-- Variável de contexto: s (dict com watched_user_id, email, active, overdue, completed_today) -->
<div class="card"
     x-data="{ expanded: false, loaded: false }"
     id="card-{{ s.watched_user_id }}"
     style="margin-bottom:8px; overflow:hidden;">

  <!-- Cabeçalho clicável -->
  <div style="display:flex; align-items:center; gap:8px; padding:12px 16px; cursor:pointer;
              border-bottom: 1px solid var(--border);"
       @click="
         expanded = !expanded;
         if (expanded && !loaded) {
           loaded = true;
           htmx.ajax('GET', '/monitoring/card/{{ s.watched_user_id }}', {
             target: '#card-body-{{ s.watched_user_id }}',
             swap: 'innerHTML'
           });
         }
       "
       :aria-expanded="expanded">

    <!-- Chevron -->
    <span x-text="expanded ? '▼' : '▶'" style="font-size:0.75rem; color:var(--text-muted); width:14px;"></span>

    <!-- Nome/Email -->
    <span style="flex:1; font-weight:500;">{{ s.email }}</span>

    <!-- Contadores -->
    <span style="font-size:0.85rem; color:var(--text-muted);">
      {{ s.active }} ativa{% if s.active != 1 %}s{% endif %}
    </span>

    {% if s.overdue > 0 %}
    <span style="font-size:0.85rem; color:var(--danger); margin-left:4px;">
      · {{ s.overdue }} atrasada{% if s.overdue > 1 %}s{% endif %}
    </span>
    {% endif %}

    {% if s.completed_today > 0 %}
    <span style="font-size:0.85rem; color:var(--success); margin-left:4px;">
      · {{ s.completed_today }} hoje
    </span>
    {% endif %}

    <!-- Botão despinar -->
    <button
      hx-delete="/monitoring/pin/{{ s.watched_user_id }}"
      hx-target="#monitoring-cards"
      hx-swap="innerHTML"
      hx-confirm="Despinar {{ s.email }}?"
      @click.stop=""
      aria-label="Despinar {{ s.email }}"
      title="Despinar"
      style="background:none; border:none; cursor:pointer; color:var(--text-muted);
             padding:4px 8px; border-radius:4px; font-size:1rem;"
      onmouseover="this.style.color='var(--danger)'"
      onmouseout="this.style.color='var(--text-muted)'">
      📌
    </button>
  </div>

  <!-- Corpo (lazy loaded) -->
  <div id="card-body-{{ s.watched_user_id }}" x-show="expanded" x-cloak style="padding:0;">
    <!-- HTMX popula aqui no primeiro expand -->
  </div>
</div>
```

- [ ] **Step 4: Criar `user_card_body.html` (tarefas agrupadas)**

```html
<!-- app/templates/partials/monitoring/user_card_body.html -->
<!-- Variáveis: groups (dict), watched_id -->
{% set priority_icon = {"critica": "🔴", "urgente": "🟠", "normal": "⚪"} %}
{% set group_labels = [
  ("atrasadas", "Atrasadas", groups.atrasadas),
  ("critica",   "Crítica",   groups.critica),
  ("urgente",   "Urgente",   groups.urgente),
  ("normal",    "Normal",    groups.normal),
] %}

<div style="padding: 8px 16px 16px;">
  {% set has_tasks = groups.atrasadas or groups.critica or groups.urgente or groups.normal %}

  {% if not has_tasks %}
    <p style="color:var(--text-muted); text-align:center; padding:16px 0;">Sem tarefas ativas 🎉</p>
  {% else %}
    {% for group_key, group_label, group_tasks in group_labels %}
      {% if group_tasks %}
        <div style="margin-top:12px;">
          <div style="font-size:0.75rem; font-weight:600; color:var(--text-muted);
                      text-transform:uppercase; letter-spacing:0.05em;
                      border-bottom:1px solid var(--border); padding-bottom:4px; margin-bottom:6px;">
            {{ group_label }}
          </div>
          {% for task in group_tasks %}
            {% set today_str = now_date %}
            <div style="display:flex; align-items:center; gap:8px; padding:6px 0;
                        border-bottom:1px solid var(--border); font-size:0.9rem;">
              <span>{{ priority_icon.get(task.priority, "⚪") }}</span>
              <span style="flex:1; overflow:hidden; text-overflow:ellipsis; white-space:nowrap;"
                    title="{{ task.name }}">
                {{ task.name }}
              </span>
              {% if task.project %}
                <span style="font-size:0.8rem; color:var(--text-muted); min-width:60px; text-align:right;">
                  {{ task.project }}
                </span>
              {% endif %}
              {% if task.deadline %}
                <span style="font-size:0.8rem; min-width:60px; text-align:right;
                             {% if task.deadline < now_date %}color:var(--danger);{% else %}color:var(--text-muted);{% endif %}">
                  {{ task.deadline[5:] }}
                </span>
              {% endif %}
            </div>
          {% endfor %}
        </div>
      {% endif %}
    {% endfor %}
  {% endif %}
</div>
```

- [ ] **Step 5: Criar `pin_picker.html` (modal de pinar)**

```html
<!-- app/templates/partials/monitoring/pin_picker.html -->
<div id="modal-overlay"
     x-data="{ search: '' }"
     style="position:fixed; inset:0; background:rgba(0,0,0,0.5); z-index:1000;
            display:flex; align-items:center; justify-content:center;"
     @click.self="document.getElementById('modal-container').innerHTML = ''"
     @keydown.escape.window="document.getElementById('modal-container').innerHTML = ''">

  <div class="card" style="width:480px; max-width:95vw; max-height:80vh;
                             display:flex; flex-direction:column; overflow:hidden;">
    <div style="display:flex; align-items:center; justify-content:space-between;
                padding:16px; border-bottom:1px solid var(--border);">
      <h3 style="margin:0; font-size:1rem;">Pinar usuários</h3>
      <button style="background:none; border:none; cursor:pointer; font-size:1.2rem; color:var(--text-muted);"
              @click="document.getElementById('modal-container').innerHTML = ''">✕</button>
    </div>

    <!-- Busca client-side -->
    <div style="padding:12px 16px; border-bottom:1px solid var(--border);">
      <input type="text" x-model="search" placeholder="Buscar por email..."
             class="form-control" style="width:100%;" autofocus>
    </div>

    <!-- Lista de usuários -->
    <div id="pin-picker-list" style="overflow-y:auto; flex:1; padding:8px 0;">
      {% include "partials/monitoring/pin_picker_list.html" %}
    </div>
  </div>
</div>
```

- [ ] **Step 6: Criar `pin_picker_list.html` (fragment: linhas do modal)**

```html
<!-- app/templates/partials/monitoring/pin_picker_list.html -->
{% for u in users %}
<div style="display:flex; align-items:center; gap:12px; padding:10px 16px;
            border-bottom:1px solid var(--border);"
     x-show="!$el.closest('[x-data]') || '{{ u.email }}'.toLowerCase().includes(search.toLowerCase())"
     x-cloak>
  <span style="flex:1; font-size:0.9rem;">{{ u.email }}</span>
  {% if u.pinned %}
    <button class="btn btn-sm btn-secondary" disabled style="min-width:80px;">✓ Pinado</button>
  {% else %}
    <form hx-post="/monitoring/pin"
          hx-target="#pin-picker-list"
          hx-swap="innerHTML"
          style="margin:0;">
      <input type="hidden" name="watched_id" value="{{ u.user_id }}">
      <button type="submit" class="btn btn-sm btn-primary" style="min-width:80px;">+ Pinar</button>
    </form>
  {% endif %}
</div>
{% else %}
<p style="color:var(--text-muted); text-align:center; padding:24px;">Nenhum usuário disponível.</p>
{% endfor %}
```

- [ ] **Step 7: Commit**

```bash
git add app/templates/partials/monitoring/
git commit -m "feat: templates monitoring (tab, cards, pin picker)"
```

---

## Task 6: Wire-up

**Files:**
- Modify: `main.py`
- Modify: `app/templates/pages/app.html`
- Modify: `app/templates/partials/sidebar.html`
- Modify: `app/routers/monitoring.py` (adicionar `now_date` ao contexto dos endpoints que usam)

- [ ] **Step 1: Registrar o router em `main.py`**

Em `main.py`, linha 8, adicionar `monitoring` ao import:

```python
from app.routers import auth, app_router, tasks, projects, presets, performance, notify, export, ideas, notes, user, bot_api, admin, monitoring
```

Após `app.include_router(admin.router)`, adicionar:

```python
app.include_router(monitoring.router)
```

- [ ] **Step 2: Adicionar `now_date` ao contexto dos endpoints de card**

Em `app/routers/monitoring.py`, o template `user_card_body.html` usa `now_date` para comparar deadlines. Atualizar o endpoint `card_body` e o helper de contexto.

Adicionar ao topo do arquivo, junto com os outros imports:
```python
from datetime import date
```

Atualizar `card_body` para passar `now_date`:
```python
@router.get("/card/{watched_id}", response_class=HTMLResponse)
async def card_body(watched_id: str, request: Request, user=Depends(require_owner)):
    client = _get_client(user)
    groups = monitoring_service.fetch_watched_user_data(
        user["user_id"], watched_id, "tasks_full", client
    )
    return templates.TemplateResponse(
        "partials/monitoring/user_card_body.html",
        {
            "request": request,
            "groups": groups,
            "watched_id": watched_id,
            "now_date": date.today().isoformat(),
        },
    )
```

- [ ] **Step 3: Adicionar `#panel-monitoring` em `app.html`**

Em `app/templates/pages/app.html`, após a linha do `#panel-admin`:

```html
    <!-- Admin -->
    <div id="panel-admin" class="tab-panel"></div>

    <!-- Acompanhamento (owner only) -->
    <div id="panel-monitoring" class="tab-panel"></div>
```

- [ ] **Step 4: Adicionar botão "Acompanhamento" na sidebar**

Em `app/templates/partials/sidebar.html`, logo após o bloco do botão Admin (dentro do `{% if user.email == owner_email %}`):

Localizar o bloco existente:
```html
{% if user.email == owner_email %}
<button class="dropdown-item" data-tab="admin"
        @click="dropdownOpen = false"
        onclick="switchTab('admin', this)"
        hx-get="/admin" hx-target="#panel-admin"
        hx-trigger="click once" hx-swap="innerHTML">
  Admin
</button>
{% endif %}
```

Substituir por:
```html
{% if user.email == owner_email %}
<button class="dropdown-item" data-tab="admin"
        @click="dropdownOpen = false"
        onclick="switchTab('admin', this)"
        hx-get="/admin" hx-target="#panel-admin"
        hx-trigger="click once" hx-swap="innerHTML">
  Admin
</button>
<button class="dropdown-item" data-tab="monitoring"
        @click="dropdownOpen = false"
        onclick="switchTab('monitoring', this)"
        hx-get="/monitoring" hx-target="#panel-monitoring"
        hx-trigger="click once" hx-swap="innerHTML">
  Acompanhamento
</button>
{% endif %}
```

- [ ] **Step 5: Testar no browser**

```powershell
cd C:\Users\campe\projetos-claude-code\JtasksApp
.\.venv\Scripts\uvicorn main:app --port 8080 --reload
```

Acessar `http://127.0.0.1:8080` com a conta do owner e verificar:
1. Dropdown do topbar mostra "Acompanhamento"
2. Clicar em "Acompanhamento" carrega a aba (sem erro 500)
3. "+ Pinar" abre o modal com a lista de usuários aprovados
4. Pinar um usuário → card aparece na aba
5. Expandir o card → tarefas do usuário aparecem agrupadas
6. Despinar → card desaparece

- [ ] **Step 6: Commit**

```bash
git add main.py app/templates/pages/app.html app/templates/partials/sidebar.html app/routers/monitoring.py
git commit -m "feat: wire-up monitoring (router + tab + sidebar)"
```

---

## Task 7: Testes de Segurança

**Files:**
- Create: `tests/__init__.py`
- Create: `tests/conftest.py`
- Create: `tests/test_monitoring_security.py`

- [ ] **Step 1: Criar `tests/__init__.py`**

```python
# tests/__init__.py
```

(arquivo vazio)

- [ ] **Step 2: Criar `tests/conftest.py`**

```python
# tests/conftest.py
import pytest
from fastapi.testclient import TestClient

from main import app
from app.services.approval_service import OWNER_EMAIL


@pytest.fixture
def client():
    with TestClient(app, raise_server_exceptions=False) as c:
        yield c


@pytest.fixture
def owner_user():
    return {
        "user_id": "owner-uuid-0000-0000-000000000000",
        "email": OWNER_EMAIL,
        "access_token": "fake-token",
        "refresh_token": "fake-refresh",
        "expires_at": 9_999_999_999,
    }


@pytest.fixture
def regular_user():
    return {
        "user_id": "other-uuid-0000-0000-000000000000",
        "email": "outro@example.com",
        "access_token": "fake-token",
        "refresh_token": "fake-refresh",
        "expires_at": 9_999_999_999,
    }
```

- [ ] **Step 3: Criar `tests/test_monitoring_security.py`**

```python
# tests/test_monitoring_security.py
"""
Testes de regressão de segurança para a feature de Acompanhamento.
Estes testes rodam sem banco de dados real.
"""
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from fastapi import HTTPException

from app.deps import get_current_user
from main import app


ANY_UUID = "00000000-0000-0000-0000-000000000000"

MONITORING_ENDPOINTS = [
    ("GET",    "/monitoring"),
    ("GET",    f"/monitoring/card/{ANY_UUID}"),
    ("GET",    f"/monitoring/refresh-all"),
    ("GET",    "/monitoring/pin-picker"),
    ("POST",   "/monitoring/pin"),
    ("DELETE", f"/monitoring/pin/{ANY_UUID}"),
]


# ── 1. Regressão: não-owner recebe 403 em TODOS os endpoints ────────────────

class TestNonOwnerGets403:
    def test_all_endpoints_return_403(self, client, regular_user):
        """
        Um usuário não-owner NÃO deve ter acesso a nenhum endpoint de monitoring.
        Testa todos os 6 endpoints definidos no router.
        """
        app.dependency_overrides[get_current_user] = lambda: regular_user

        try:
            for method, path in MONITORING_ENDPOINTS:
                resp = client.request(method, path)
                assert resp.status_code == 403, (
                    f"{method} {path} retornou {resp.status_code} — esperado 403. "
                    f"Conteúdo: {resp.text[:200]}"
                )
        finally:
            app.dependency_overrides.clear()

    def test_unauthenticated_gets_403(self, client):
        """Requisição sem sessão deve receber 403 (não redirect) nos endpoints HTMX."""
        # Sem dependency override — sessão vazia → get_current_user retorna RedirectResponse
        # require_owner converte RedirectResponse em HTTPException(403)
        for method, path in MONITORING_ENDPOINTS:
            resp = client.request(method, path, allow_redirects=False)
            # Aceita 403 ou redirect para login (302) — o importante é não retornar 200
            assert resp.status_code in (302, 403), (
                f"{method} {path} retornou {resp.status_code} sem autenticação"
            )


# ── 2. Validação de pin: watched_id não pinado → 404 ───────────────────────

class TestFetchRejectsNonPinnedUser:
    def test_fetch_raises_404_for_non_pinned(self):
        """
        fetch_watched_user_data deve levantar HTTPException(404)
        quando watched_id não está nos pinados do owner.
        """
        from app.services.monitoring_service import fetch_watched_user_data

        # Mock do user_client: watched_users retorna lista vazia (não pinado)
        mock_client = MagicMock()
        (
            mock_client.table.return_value
            .select.return_value
            .eq.return_value
            .eq.return_value
            .limit.return_value
            .execute.return_value
            .data
        ) = []

        with pytest.raises(HTTPException) as exc_info:
            fetch_watched_user_data(
                owner_id="owner-uuid",
                watched_id="random-uuid-not-pinned",
                resource="tasks_full",
                user_client=mock_client,
            )

        assert exc_info.value.status_code == 404

    def test_fetch_succeeds_for_pinned_user(self):
        """
        fetch_watched_user_data deve funcionar quando watched_id está pinado.
        """
        from app.services.monitoring_service import fetch_watched_user_data

        mock_client = MagicMock()
        # Simula pin encontrado
        (
            mock_client.table.return_value
            .select.return_value
            .eq.return_value
            .eq.return_value
            .limit.return_value
            .execute.return_value
            .data
        ) = [{"id": "some-pin-id"}]

        watched_id = "pinned-user-uuid"

        with patch("app.services.monitoring_service.get_service_client") as mock_svc:
            mock_svc_client = MagicMock()
            mock_svc.return_value = mock_svc_client
            (
                mock_svc_client.table.return_value
                .select.return_value
                .eq.return_value
                .eq.return_value
                .execute.return_value
                .data
            ) = []  # Nenhuma tarefa — retorno válido

            result = fetch_watched_user_data(
                owner_id="owner-uuid",
                watched_id=watched_id,
                resource="tasks_full",
                user_client=mock_client,
            )

        # Deve retornar o dict de grupos (possivelmente vazio)
        assert isinstance(result, dict)
        assert "atrasadas" in result
        assert "critica" in result


# ── 3. Auditoria estática: service_client NÃO no router ────────────────────

class TestStaticAudit:
    def test_service_client_not_in_monitoring_router(self):
        """
        REGRA DE OURO: app/routers/monitoring.py não deve importar nem referenciar
        get_service_client() ou service_client.
        Falha aqui significa que um futuro endpoint pode vazar dados sem o helper de validação.
        """
        content = Path("app/routers/monitoring.py").read_text(encoding="utf-8")
        assert "get_service_client" not in content, (
            "get_service_client encontrado em monitoring.py — "
            "mova para monitoring_service.py"
        )
        assert "service_client" not in content, (
            "service_client encontrado em monitoring.py — "
            "mova para monitoring_service.py"
        )

    def test_monitoring_service_has_service_client(self):
        """
        monitoring_service.py DEVE ter get_service_client (confirma que o helper existe).
        """
        content = Path("app/services/monitoring_service.py").read_text(encoding="utf-8")
        assert "get_service_client" in content
```

- [ ] **Step 4: Instalar pytest se necessário e rodar os testes**

```bash
cd c:/Users/campe/projetos-claude-code/JtasksApp
.venv/Scripts/pip install pytest -q
.venv/Scripts/pytest tests/test_monitoring_security.py -v
```

Esperado — todos os testes devem passar:
```
tests/test_monitoring_security.py::TestNonOwnerGets403::test_all_endpoints_return_403 PASSED
tests/test_monitoring_security.py::TestNonOwnerGets403::test_unauthenticated_gets_403 PASSED
tests/test_monitoring_security.py::TestFetchRejectsNonPinnedUser::test_fetch_raises_404_for_non_pinned PASSED
tests/test_monitoring_security.py::TestFetchRejectsNonPinnedUser::test_fetch_succeeds_for_pinned_user PASSED
tests/test_monitoring_security.py::TestStaticAudit::test_service_client_not_in_monitoring_router PASSED
tests/test_monitoring_security.py::TestStaticAudit::test_monitoring_service_has_service_client PASSED
```

- [ ] **Step 5: Commit**

```bash
git add tests/
git commit -m "test: regressão de segurança para monitoring (403, 404, auditoria estática)"
```

---

## Self-Review — Cobertura do Spec

| Requisito do Spec | Task |
|---|---|
| Aba "Acompanhamento" visível apenas ao owner | T6: sidebar condicional + require_owner |
| Owner pina/despina via modal | T4: POST /pin + DELETE /pin/{id}; T5: pin_picker.html |
| Cards colapsados por padrão | T5: user_card.html (x-data expanded=false) |
| Expansão lazy on-demand | T5: htmx.ajax no @click com flag `loaded` |
| Tarefas: Atrasadas → Crítica → Urgente → Normal por deadline ASC | T3: _group_tasks() |
| Contadores: ativas, atrasadas (vermelho), hoje (verde) | T3: get_all_summaries(); T5: user_card.html |
| Polling 30s toggleável | T5: monitoring_tab.html Alpine x-data |
| Botão refresh reseta timer | T5: manualRefresh() chama startTimer() |
| Indicador "Atualizado há Xs" | T5: secondsAgo reativo no Alpine |
| 4 travas de segurança | T2 (gate), T3 (helper), T1 (RLS), T7 (testes) |
| grep service_client monitoring.py → zero | T4 step 2 + T7 auditoria estática |
| Migration sem impacto nos usuários existentes | T1: CREATE TABLE only |
| Estado vazio sem pinados | T5: user_cards_list.html |
| Estado vazio sem tarefas | T5: user_card_body.html |
