# Sistema de Permissões (Master + Feature Flags por Usuário)

**Data:** 2026-04-16
**Autor:** Jefferson Campelo (via brainstorming colaborativo)
**Status:** Design aprovado, aguardando plano de implementação

---

## Contexto e Motivação

A aplicação JtasksApp está crescendo. A primeira feature gated por owner (`monitoring`, "Acompanhamento de Usuários") foi implementada com a dependency `require_owner`, que checa se o email do usuário corresponde ao `OWNER_EMAIL` hardcoded. Esse modelo funciona para uma única feature owner-only, mas não escala para o roadmap previsto:

- Outras features (relatórios da empresa, exports avançados, templates compartilhados) precisarão ser habilitadas seletivamente para alguns usuários (supervisores), não apenas para o owner.
- O owner precisa de uma interface para conceder/revogar essas features sem editar código ou banco.
- Cada feature deve seguir o mesmo padrão de gate, evitando duplicação e proliferação de checagens ad-hoc.

Este design propõe um sistema genérico de **feature flags por usuário**, controlado integralmente pelo master (owner hardcoded), aplicável a qualquer feature presente ou futura.

---

## Decisões de Escopo (validadas com o usuário)

| Decisão | Escolha | Por quê |
|---------|---------|---------|
| Quem é master? | `OWNER_EMAIL` hardcoded (mesma constante atual) | Cenário pequeno, controlado pelo dono. Sem necessidade de RBAC dinâmico. |
| Visibilidade dos supervisores | Gate binário — todos com a feature vêem a mesma lista global | Simplifica modelo de dados. Sem `supervisor_id` em `watched_users`. |
| Generalização | Tabela `user_features` genérica para qualquer feature | Outras features já estão no roadmap (B confirmado). |
| Auditoria | Mínima: `user_id`, `feature`, `enabled_at`. Revoga = DELETE | Master único, sem requisito de compliance. YAGNI. |
| UI admin | Item no menu do perfil (não na sidebar) | Não polui navegação principal de quem não é master. |

---

## Arquitetura em 4 Camadas de Proteção

```
┌─────────────────────────────────────────────────────────────┐
│  Camada 1 — RLS no Supabase                                  │
│  user_features: SELECT só linhas do próprio user;            │
│  INSERT/UPDATE/DELETE negado pra todos via RLS               │
└─────────────────────────────────────────────────────────────┘
                          ↓
┌─────────────────────────────────────────────────────────────┐
│  Camada 2 — Gate no router                                   │
│  require_feature("monitoring") → 403 se sem acesso           │
│  require_owner → 403 se não-master (só painel admin)         │
└─────────────────────────────────────────────────────────────┘
                          ↓
┌─────────────────────────────────────────────────────────────┐
│  Camada 3 — Service layer                                    │
│  permissions_service.py centraliza writes (service_key)      │
│  grant/revoke validam is_owner internamente                  │
└─────────────────────────────────────────────────────────────┘
                          ↓
┌─────────────────────────────────────────────────────────────┐
│  Camada 4 — Auditoria estática (testes)                      │
│  Garante que routers nunca importam get_service_client       │
│  Garante que require_owner não vaza pra outras features      │
└─────────────────────────────────────────────────────────────┘
```

---

## Seção 1 — Modelo de Dados

### Tabela `user_features`

```sql
create table public.user_features (
    user_id     uuid not null references auth.users(id) on delete cascade,
    feature     text not null,
    enabled_at  timestamptz not null default now(),
    primary key (user_id, feature)
);

create index user_features_feature_idx on public.user_features(feature);
```

### RLS

```sql
alter table public.user_features enable row level security;

-- SELECT: usuário lê apenas suas próprias linhas
create policy user_features_select_own on public.user_features
    for select using (auth.uid() = user_id);

-- INSERT/UPDATE/DELETE: negado a todos (somente service_key bypassa)
-- Sem policy = bloqueio total para clientes anon/authenticated
```

**Migration:** `migrations/2026-04-16_user_features.sql`, aplicada manualmente no SQL Editor do Supabase (mesmo padrão do `watched_users`).

### Constantes de features (no código)

```python
# app/services/permissions_service.py
KNOWN_FEATURES: set[str] = {"monitoring"}
```

A enumeração explícita evita erros de digitação em endpoints (`"monitorring"`) e serve como ponto único de adição de novas features.

---

## Seção 2 — Service Layer (`permissions_service.py`)

### Localização
`app/services/permissions_service.py` — arquivo novo.

### Responsabilidades
- Centralizar TODA lógica de verificação e mutação de permissões.
- Cache de features por request (evita N queries no mesmo render).
- Único arquivo autorizado a chamar `get_service_client()` para escrever em `user_features`.

### API pública

```python
OWNER_EMAIL = "campelo.jefferson@gmail.com"
KNOWN_FEATURES: set[str] = {"monitoring"}

def is_owner(user: dict) -> bool:
    """True se o email do usuário corresponde ao OWNER_EMAIL."""

def get_user_features(user: dict, request: Request) -> set[str]:
    """
    Retorna set de features ativas do usuário.
    - Owner sempre recebe KNOWN_FEATURES (features implícitas).
    - Demais usuários: query em user_features filtrando por user_id.
    - Resultado cacheado em request.state.user_features para reutilização.
    """

def has_feature(user: dict, request: Request, feature: str) -> bool:
    """Atalho: feature in get_user_features(user, request)."""

def grant_feature(target_user_id: str, feature: str, master_user: dict) -> None:
    """
    Concede feature a um usuário.
    - Valida is_owner(master_user) → HTTP 403 se falhar.
    - Valida feature in KNOWN_FEATURES → HTTP 400 se desconhecida.
    - Usa service_key (UPSERT) para bypassar RLS de escrita.
    """

def revoke_feature(target_user_id: str, feature: str, master_user: dict) -> None:
    """
    Revoga feature (DELETE).
    - Valida is_owner(master_user) → HTTP 403 se falhar.
    - Idempotente (DELETE de linha inexistente é no-op).
    """

def list_users_with_features(master_user: dict) -> list[dict]:
    """
    Lista todos os usuários (exceto o master) com suas features ativas.
    - Valida is_owner → HTTP 403 se falhar.
    - Usa service_key para acessar auth.users + user_features.
    - Retorno: [{"user_id", "email", "features": set[str]}]
    """
```

### Princípios

1. **Nenhum router** deve importar `get_service_client` — esta regra será validada por teste estático.
2. **Toda checagem de feature** passa por `has_feature()` ou `get_user_features()`.
3. **Cache em request.state** evita query duplicada no mesmo ciclo de request (ex: sidebar + endpoint de monitoring no mesmo render).
4. **Owner é implícito** — sempre recebe todas as `KNOWN_FEATURES` sem precisar de linhas físicas em `user_features`.

---

## Seção 3 — Gates e Dependencies (`app/deps.py`)

### `require_owner` (mantido, escopo reduzido)

```python
def require_owner(user=Depends(get_current_user)):
    """
    Gate exclusivo para administração de permissões.
    Uso permitido APENAS em routers de admin/master (ex: /admin/permissions/).
    """
    if isinstance(user, RedirectResponse):
        raise HTTPException(403, "Não autenticado")
    if not is_owner(user):
        raise HTTPException(403, "Acesso negado")
    return user
```

### `require_feature(feature_name)` (factory novo)

```python
def require_feature(feature: str):
    """
    Factory que retorna dependency validando acesso à feature.
    Owner sempre passa (via features implícitas em get_user_features).
    """
    def _check(request: Request, user=Depends(get_current_user)):
        if isinstance(user, RedirectResponse):
            raise HTTPException(403, "Não autenticado")
        if not has_feature(user, request, feature):
            raise HTTPException(403, "Acesso negado")
        return user
    return _check
```

### Convenção de uso

| Gate | Quando usar |
|------|-------------|
| `require_feature("X")` | Features de produto (monitoring, exports avançados, etc.) |
| `require_owner` | Apenas administração de permissões — `/admin/permissions/*` |
| `get_current_user` | Endpoints abertos a qualquer usuário autenticado |

---

## Seção 4 — UI Admin (Painel de Permissões)

### Acesso
Item novo no menu do perfil/header (topo direito da aplicação), visível **apenas se `is_owner`**:

```html
{% if is_owner %}
<a hx-get="/admin/permissions/"
   hx-target="#modal-container"
   hx-swap="innerHTML">
   Permissões
</a>
{% endif %}
```

### Endpoints (`app/routers/admin_permissions.py` — novo)

```python
router = APIRouter(
    prefix="/admin/permissions",
    dependencies=[Depends(require_owner)],
)

@router.get("/")           # Renderiza modal com lista de usuários + features
@router.post("/grant")     # Form: user_id, feature → grant_feature()
@router.post("/revoke")    # Form: user_id, feature → revoke_feature()
```

### Layout do modal

```
┌─────────────────────────────────────────────────────┐
│  Gerenciar Permissões                          [×]  │
├─────────────────────────────────────────────────────┤
│  Conceda features a usuários específicos.           │
│                                                      │
│  ┌───────────────────────────────────────────────┐ │
│  │ 👤 joao@email.com                             │ │
│  │    ☑ monitoring          (concedida 10/04)    │ │
│  ├───────────────────────────────────────────────┤ │
│  │ 👤 maria@email.com                            │ │
│  │    ☐ monitoring                               │ │
│  └───────────────────────────────────────────────┘ │
│                                                      │
│                              [Fechar]               │
└─────────────────────────────────────────────────────┘
```

### Comportamento

- Lista todos os usuários **exceto o próprio master**.
- Cada feature em `KNOWN_FEATURES` aparece como checkbox ao lado do email.
- Marcar/desmarcar dispara HTMX direto (sem botão "Salvar"):

```html
<input type="checkbox"
       {% if "monitoring" in user.features %}checked{% endif %}
       hx-post="/admin/permissions/{{ 'revoke' if 'monitoring' in user.features else 'grant' }}"
       hx-vals='{"user_id": "{{ user.id }}", "feature": "monitoring"}'
       hx-swap="outerHTML"
       hx-target="closest .user-row">
```

- Após cada toggle, re-renderiza apenas a linha do usuário (`outerHTML` em `.user-row`).
- Toast de feedback: "Feature 'monitoring' concedida a joao@email.com" via `HX-Trigger`.

### Templates novos

```
app/templates/partials/admin/
  ├── permissions_modal.html       # Container do modal
  ├── permissions_user_list.html   # Lista de usuários
  └── permissions_user_row.html    # Linha individual (re-renderizada no toggle)
```

---

## Seção 5 — Integração com Sidebar e Templates

### Helper de contexto centralizado

**Arquivo novo:** `app/template_context.py`

```python
from fastapi import Request
from app.services.permissions_service import is_owner, get_user_features

def build_user_context(request: Request, user: dict) -> dict:
    """Contexto comum injetado em todos os renders de página com sidebar."""
    return {
        "user": user,
        "is_owner": is_owner(user),
        "user_features": get_user_features(user, request),
    }
```

### Aplicação no shell

`app/routers/app_router.py`:

```python
@router.get("/app")
async def app_shell(request: Request, user=Depends(get_current_user)):
    if isinstance(user, RedirectResponse):
        return user
    return templates.TemplateResponse(
        "pages/app.html",
        {
            "request": request,
            "css_version": _css_version(),
            **build_user_context(request, user),
        },
    )
```

### Sidebar atualizado

`app/templates/partials/sidebar.html`:

```html
{% if "monitoring" in user_features %}
<button hx-get="/monitoring/" hx-target="#panel-monitoring">
    Acompanhamento
</button>
{% endif %}
```

### Header / menu do perfil

```html
{% if is_owner %}
<a hx-get="/admin/permissions/" hx-target="#modal-container">Permissões</a>
{% endif %}
```

### Por que dois flags separados?

| Flag | Uso |
|------|-----|
| `is_owner` | Gates de **administração** (painel master) |
| `user_features` | Gates de **produto** (tabs/features visíveis) |

Owner tem `is_owner = True` E `"monitoring" in user_features` (via features implícitas). Sidebar não precisa de `or is_owner` — a checagem de feature já cobre.

### Partials HTMX

Partials que retornam fragmentos isolados geralmente não precisam desse contexto. Quando precisarem, basta espalhar `**build_user_context(request, user)` no `TemplateResponse`.

---

## Seção 6 — Migração da Feature Monitoring Atual

### Mudanças cirúrgicas (sem refactor)

**1. `app/routers/monitoring.py`:**
```python
# ANTES
from app.deps import require_owner
router = APIRouter(prefix="/monitoring", dependencies=[Depends(require_owner)])

# DEPOIS
from app.deps import require_feature
router = APIRouter(
    prefix="/monitoring",
    dependencies=[Depends(require_feature("monitoring"))],
)
```

**2. `app/templates/partials/sidebar.html`:**
```html
<!-- ANTES -->
{% if is_owner %}
<button hx-get="/monitoring/">Acompanhamento</button>
{% endif %}

<!-- DEPOIS -->
{% if "monitoring" in user_features %}
<button hx-get="/monitoring/">Acompanhamento</button>
{% endif %}
```

**3. `app/routers/app_router.py`:** injetar `**build_user_context(request, user)` no render do `/app`.

### O que NÃO muda

- `monitoring_service.py` — toda lógica de fetch/group/pin permanece.
- `watched_users` (tabela) — global, sem `supervisor_id`.
- `monitoring_pins` (se existir) — pins continuam per-user (cada supervisor tem suas pins).
- RLS de `watched_users` — sem mudança (service_key bypassa, gate no router).
- Templates `partials/monitoring/*` — funcionam para qualquer usuário com a feature.

### Verificação pós-migração

Rodar busca global para garantir que nenhum outro endpoint usava `require_owner`:

```bash
grep -rn "require_owner" app/
```

**Esperado:** apenas `app/deps.py` (definição) e `app/routers/admin_permissions.py` (gate do painel).

### Riscos e mitigações

| Risco | Mitigação |
|-------|-----------|
| Supervisor habilitado vê dados de outros usuários via `watched_users` | Comportamento desejado (gate binário, decisão de escopo confirmada) |
| Esquecer de aplicar a migration `user_features` no Supabase | Documentar no plano de implementação como passo manual obrigatório |
| Sidebar quebrar se contexto faltar `user_features` | `build_user_context` sempre retorna `set()` (vazio), nunca `None`/undefined |
| Master perder acesso em algum endpoint após migração | Owner tem features implícitas (`KNOWN_FEATURES`), sempre passa em `require_feature` |

---

## Seção 7 — Testes de Regressão de Segurança

### Arquivo novo: `tests/test_permissions_security.py`

### Categoria 1 — `permissions_service` (unit)

- `test_is_owner_true_for_owner_email`
- `test_is_owner_false_for_other_email`
- `test_owner_implicit_features` — owner recebe `KNOWN_FEATURES` sem precisar de linha no banco
- `test_grant_feature_rejects_non_owner` — HTTP 403 se chamado sem master
- `test_grant_feature_rejects_unknown_feature` — HTTP 400 se feature não está em `KNOWN_FEATURES`
- `test_revoke_feature_rejects_non_owner` — HTTP 403
- `test_revoke_feature_idempotent` — DELETE de linha inexistente não falha

### Categoria 2 — Gates (integração com TestClient)

- `test_monitoring_endpoint_blocks_user_without_feature` — usuário sem `monitoring` recebe 403
- `test_monitoring_endpoint_allows_user_with_feature` — usuário com `monitoring` recebe 200
- `test_monitoring_endpoint_allows_owner` — owner sempre passa via features implícitas
- `test_admin_permissions_blocks_supervisor` — mesmo supervisor recebe 403 em `/admin/permissions/`
- `test_admin_permissions_allows_only_owner`

### Categoria 3 — Auditoria estática (file scan)

- `test_no_router_imports_get_service_client` — varre `app/routers/*.py`, falha se algum importar `get_service_client`
- `test_user_features_writes_only_in_permissions_service` — busca por `.table("user_features").insert/update/delete` em todo o projeto, exceto `permissions_service.py`
- `test_require_owner_only_in_admin_permissions` — `require_owner` só pode aparecer em `app/deps.py` e `app/routers/admin_permissions.py`

### Categoria 4 — RLS (manual, documentado)

Não automatizado (exige Supabase real). Adicionar como **checklist manual** ao final do plano de implementação:

```
□ Logar como supervisor → tentar INSERT em user_features via REST direto → deve falhar (RLS)
□ Logar como user comum → SELECT em user_features → retorna apenas suas próprias linhas
□ Master via service_key → INSERT/DELETE funciona normalmente
```

### Cobertura por camada

| Camada | Como protege | Tipo de teste |
|--------|--------------|---------------|
| RLS Supabase | Bloqueia escrita direta via REST | Manual |
| Gate de router | Bloqueia HTTP a quem não tem feature | Integração |
| Service helper | Valida `is_owner` antes de escrever | Unit |
| Auditoria estática | Garante que dev futuro não fure as regras | Estático (file scan) |

---

## Estrutura Final de Arquivos

### Arquivos novos

```
migrations/2026-04-16_user_features.sql
app/services/permissions_service.py
app/routers/admin_permissions.py
app/template_context.py
app/templates/partials/admin/permissions_modal.html
app/templates/partials/admin/permissions_user_list.html
app/templates/partials/admin/permissions_user_row.html
tests/test_permissions_security.py
```

### Arquivos modificados

```
app/deps.py                                  (+ require_feature factory)
app/routers/monitoring.py                    (require_owner → require_feature)
app/routers/app_router.py                    (+ build_user_context no shell)
app/templates/partials/sidebar.html          (is_owner → "monitoring" in user_features)
app/templates/partials/header.html (ou local do menu do perfil)  (+ item Permissões)
main.py                                      (+ include admin_permissions router)
```

---

## Critérios de Aceitação

1. ✅ Migration aplicada no Supabase, RLS verificado manualmente.
2. ✅ `permissions_service.py` criado com todas as funções da API pública (Seção 2).
3. ✅ `require_feature` factory funcional em `app/deps.py`.
4. ✅ Router `/monitoring/*` migrado para `require_feature("monitoring")`.
5. ✅ Painel admin acessível via menu do perfil, com toggle funcional.
6. ✅ Sidebar mostra "Acompanhamento" para owner E para supervisores com a feature.
7. ✅ Owner sem nenhuma linha em `user_features` continua acessando todas as features (implícitas).
8. ✅ Supervisor recebe 403 ao tentar acessar `/admin/permissions/`.
9. ✅ Todos os testes de `tests/test_permissions_security.py` passam.
10. ✅ Checklist manual de RLS validado contra Supabase real.

---

## Itens Fora de Escopo (Decisões Adiadas)

- **RBAC com múltiplos roles** — adiado até cenário escalar para múltiplos masters/clientes.
- **Auditoria de histórico** (quem concedeu, quando revogou) — adiado até requisito real surgir.
- **Segmentação por time** (`supervisor_id` em `watched_users`) — não necessário no escopo atual; supervisor vê lista global.
- **Self-service de features** (usuário pedir acesso) — adiado; concessão é exclusiva do master.
- **Expiração automática de features** — não necessário no escopo controlado manual.

---

## Próximo Passo

Plano de implementação detalhado a ser gerado pela skill `superpowers:writing-plans` em sessão futura, com tasks ordenadas, dependências entre arquivos e checklist de validação por etapa.
