# CLAUDE.md — Diretrizes do Projeto JtasksApp

## Visão Geral

JtasksApp é um gerenciador de tarefas corporativo multi-tenant. Cada usuário tem sessão, dados e configurações completamente isolados.

**Stack:** FastAPI + HTMX + Alpine.js + Jinja2 + Supabase + APScheduler

---

## REGRA #1 — Isolamento de Dados por Usuário

**Toda query ao Supabase DEVE filtrar por `user_id`.** Sem exceção.

```python
# CORRETO
client.table("tasks").select("*").eq("user_id", user["user_id"]).execute()

# ERRADO — nunca fazer isso
client.table("tasks").select("*").execute()
```

### Onde isso se aplica:
- **Todas as tabelas:** tasks, projects, presets, task_updates, task_checklist
- **Todos os endpoints:** leitura, escrita, exclusão, filtros, exports, performance
- **Service key (email_service.py):** A service_key do Supabase **bypassa RLS**. Queries com service_key DEVEM incluir filtro `user_id` explícito na URL REST
- **Configs locais (notify):** Armazenadas em `configs/notify_{user_id}.json` — nunca usar config global

### Checklist para novos endpoints:
1. Usar `user=Depends(get_current_user)` como dependência
2. Verificar `if isinstance(user, RedirectResponse): return user`
3. Criar client com `get_user_client(user["access_token"], user["refresh_token"])`
4. Adicionar `.eq("user_id", user["user_id"])` em TODA query
5. Se usar service_key (REST direto), incluir `&user_id=eq.{user_id}` na URL

---

## Autenticação

### Padrão obrigatório em todo endpoint protegido:
```python
from app.deps import get_current_user

async def meu_endpoint(request: Request, user=Depends(get_current_user)):
    if isinstance(user, RedirectResponse):
        return user
    # user["user_id"], user["access_token"], user["refresh_token"], user["email"]
```

### Sessão do usuário (modelo server-side):

- `request.session` guarda **apenas** `session_id` (UUID)
- Os tokens (`access_token`, `refresh_token`, `expires_at`) ficam na tabela `app_sessions` no Supabase
- `get_current_user()` busca a sessão server-side e entrega ao router um dict com `user_id`, `email`, `access_token` e `refresh_token` — a interface dos routers não muda
- O token é renovado automaticamente em `deps.py` quando faltam < 60s para expirar, atualizando `app_sessions`
- Login via Supabase Auth (`sign_in_with_password`)
- Sessão gerenciada pelo `SessionMiddleware` do Starlette + `app/services/session_service.py`

---

## Estrutura do Projeto

```
JtasksApp/
├── main.py                          # Entry point FastAPI + lifespan (scheduler)
├── app/
│   ├── config.py                    # Pydantic Settings (.env)
│   ├── deps.py                      # get_current_user (auth dependency)
│   ├── scheduler.py                 # APScheduler — jobs por usuário
│   ├── routers/
│   │   ├── auth.py                  # /auth/login, /auth/logout
│   │   ├── app_router.py           # /, /app (shell principal)
│   │   ├── tasks.py                 # CRUD tarefas, filtros, calendário, updates, checklist
│   │   ├── projects.py             # CRUD projetos
│   │   ├── presets.py              # CRUD presets + aplicar presets
│   │   ├── performance.py          # /performance/data (JSON para charts)
│   │   ├── notify.py               # Config SMTP + envio manual
│   │   └── export.py               # Export Excel (.xlsx)
│   ├── services/
│   │   ├── supabase_client.py      # get_user_client() e get_service_client()
│   │   ├── email_service.py        # build_email_html() + send_email()
│   │   └── notify_config.py        # Config per-user em JSON local
│   └── templates/
│       ├── base.html                # Layout base (CDNs, Alpine, HTMX)
│       ├── login.html
│       ├── pages/app.html           # Shell com tabs lazy-loaded
│       └── partials/                # Componentes reutilizáveis
│           ├── sidebar.html
│           ├── toast.html
│           ├── tasks/               # task_list, task_item_active, etc.
│           ├── modals/              # edit, complete, presets, updates
│           ├── calendar/
│           ├── checklist/
│           ├── performance/
│           ├── projects/
│           └── notify/
├── static/
│   ├── css/app.css                  # JEMS Design System
│   └── js/charts.js                # Chart.js (performance)
├── configs/                         # Configs SMTP por usuário (gitignored)
├── .env                             # Variáveis de ambiente (gitignored)
└── .github/workflows/deploy.yml    # CI/CD → VPS via SSH
```

---

## Banco de Dados (Supabase)

### Tabelas principais:
| Tabela | Campos-chave | Relações |
|--------|-------------|----------|
| tasks | id, user_id, name, project, priority, status, deadline, created_at, completed_at | task_updates (1:N), task_checklist (1:N) |
| projects | id, user_id, name (unique por user) | — |
| presets | id, user_id, name, project, priority | — |
| task_updates | id, task_id, user_id, text, created_at | — |
| task_checklist | id, task_id, user_id, text, done, position | — |

### Clientes Supabase:
- **`get_user_client(access_token, refresh_token)`** — Usa anon_key + JWT do usuário. Usar em endpoints de API.
- **`get_service_client()`** — Usa service_key, **bypassa RLS**. Usar APENAS em jobs server-side (email_service). SEMPRE filtrar por user_id manualmente.

### Prioridades:
- `critica` (vermelho), `urgente` (laranja), `normal` (cinza)
- Ordenação customizada no Python: `{"critica": 0, "urgente": 1, "normal": 2}`

### Status:
- `active`, `completed`, `discarded`, `pending`

---

## Frontend — Padrões HTMX + Alpine.js

### Navegação por tabs (lazy loading):
```html
<!-- Tabs carregam conteúdo via HTMX no primeiro clique -->
hx-get="/tasks" hx-target="#panel-ativas" hx-trigger="click" hx-swap="innerHTML"
```

### Modais:
- Carregados via HTMX em `#modal-container`
- Fechados via JS: `document.getElementById('modal-container').innerHTML = ''`

### Toast notifications:
```python
response.headers["HX-Trigger"] = json.dumps({"showToast": "Mensagem aqui"})
```

### Refresh após ações:
```python
response.headers["HX-Trigger"] = json.dumps({
    "showToast": "Tarefa criada!",
    "refreshTasks": True
})
```

### CSS cache-busting:
- `app_router.py` e `auth.py` passam `css_version` (mtime do arquivo) para o template
- Template usa: `href="/static/css/app.css?v={{ css_version }}"`

---

## Scheduler (APScheduler)

- Um job por usuário habilitado: `email_daily_{user_id}`
- `reschedule()` é chamado toda vez que um usuário salva config de notificação
- Configs lidas de `configs/notify_{user_id}.json` via `load_all_configs()`
- O scheduler inicia/para no lifespan do FastAPI (`main.py`)

---

## Deploy (CI/CD)

**Trigger:** push na branch `master`

**Fluxo no VPS:**
```bash
git fetch origin master
git reset --hard origin/master    # Força sync — NUNCA usar git pull
pip install -r requirements.txt
sudo systemctl restart jtasks
```

- O `git reset --hard` é intencional — evita conflitos com alterações locais no VPS
- O serviço roda como systemd unit `jtasks`

### Variáveis de ambiente no servidor (.env):
```
SUPABASE_URL, SUPABASE_ANON_KEY, SUPABASE_SERVICE_KEY, SECRET_KEY
```

---

## Convenções de Código

### Python:
- Idioma do código: **inglês** (nomes de funções, variáveis)
- Idioma da UI/mensagens: **português brasileiro**
- Responses HTML inline para feedback HTMX simples: `HTMLResponse('<span>...</span>')`
- Templates para componentes reutilizáveis: `templates.TemplateResponse(...)`

### Templates Jinja2:
- Herança: `base.html` → `pages/app.html` → `partials/`
- Partials nunca extendem base — são fragmentos HTML retornados via HTMX

### CSS:
- Design system: JEMS (navy `#0D1F35`, teal `#0B8B78`)
- Breakpoint mobile: `1024px` (cobre tablets)
- Dark mode via CSS variables + toggle Alpine.js

---

## Arquivos sensíveis (gitignored)

- `.env` — Chaves Supabase + secret key
- `configs/` — Contém senhas SMTP dos usuários
- `config.json` / `config.json.migrated` — Config legada

---

## Ambiente Local (Desenvolvimento)

### Subindo a aplicação (Windows PowerShell):
```powershell
cd C:\Users\campe\projetos-claude-code\JtasksApp
.\.venv\Scripts\uvicorn main:app --port 8080 --reload
```
Acesse em `http://127.0.0.1:8080`

### Após puxar mudanças da VPS ou do git:
Sempre atualizar o `.venv` local para evitar incompatibilidades de dependências:
```powershell
.\.venv\Scripts\pip install -r requirements.txt
```

> **Causa de um incidente real:** o `.venv` local estava com `supabase==2.9.0` enquanto o `requirements.txt` exigia `2.28.3`. A versão antiga não suportava o novo formato de chaves do Supabase (`sb_publishable_...` / `sb_secret_...`), causando `Invalid API key` na criação do client e impedindo o login.

---

## Erros Comuns a Evitar

1. **Query sem filtro user_id** — Vaza dados entre usuários
2. **Usar `get_service_client()` em endpoints** — Bypassa RLS. Usar `get_user_client()`
3. **Config de notificação global** — Sempre per-user via `load_config(user_id)`
4. **`git pull` no deploy** — Falha silenciosamente se houver conflito local. Usar `git reset --hard`
5. **Template usando variável não definida** — Se o router não passar a variável, Jinja2 lança `UndefinedError` e HTMX falha silenciosamente
6. **Esquecer `css_version` no context** — CSS fica cacheado indefinidamente no mobile
7. **`.venv` desatualizado** — Após puxar mudanças, sempre rodar `pip install -r requirements.txt`. Versões antigas da lib `supabase` não suportam as novas chaves `sb_publishable_` / `sb_secret_`
