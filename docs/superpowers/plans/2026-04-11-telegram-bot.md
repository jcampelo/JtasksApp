# Bot Telegram — Plano de Implementação

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implementar um bot do Telegram que funciona como interface completa ao JtasksApp — captura rápida por voz ou texto, gestão de tarefas/notas/ideias com botões inline para desambiguação.

**Architecture:** O bot roda como processo Python separado (`bot/bot.py`) e se comunica com o JtasksApp via HTTP interno com API Key. O JtasksApp expõe novos endpoints JSON em `/bot/*` que usam o service client do Supabase (filtrado por `BOT_OWNER_USER_ID`). O LLM (Groq LLaMA) interpreta as mensagens e o Groq Whisper transcreve áudios.

**Tech Stack:** `python-telegram-bot` v20, `groq` SDK, `httpx`, FastAPI (existente), Supabase service client (existente).

---

## Arquivos criados/modificados

| Arquivo | Ação | Responsabilidade |
|---|---|---|
| `app/config.py` | Modificar | Adicionar variáveis do bot |
| `app/routers/bot_api.py` | Criar | Endpoints JSON exclusivos para o bot |
| `main.py` | Modificar | Registrar router do bot |
| `requirements.txt` | Modificar | Adicionar dependências |
| `bot/__init__.py` | Criar | Torna `bot/` um pacote Python |
| `bot/prompts.py` | Criar | Prompt do sistema para o LLaMA |
| `bot/groq_client.py` | Criar | STT (Whisper) + NLP (LLaMA) |
| `bot/formatters.py` | Criar | Formata mensagens de resposta do bot |
| `bot/actions.py` | Criar | Chamadas HTTP aos endpoints do JtasksApp |
| `bot/bot.py` | Criar | Handlers do Telegram, comandos, botões inline |

---

## FASE 1 — Pré-requisitos (você faz antes de começar)

> ⚠️ Estes passos são manuais e devem ser feitos por você antes de qualquer implementação de código.

### Task 0: Pré-requisitos manuais

**0.1 — Criar o bot no Telegram**

- [ ] Abra o Telegram e pesquise por `@BotFather`
- [ ] Envie a mensagem `/newbot`
- [ ] Escolha um nome (ex: "Jtasks Bot") e um username (ex: `jtasksapp_bot`)
- [ ] Copie o token que o BotFather enviar (formato: `123456789:ABC...`). **Guarde esse token.**
- [ ] Ainda no BotFather, envie `/setcommands` e selecione seu bot
- [ ] Cole o seguinte bloco de comandos:
```
tarefas - Lista tarefas ativas
hoje - Tarefas com prazo para hoje
atrasadas - Tarefas com prazo vencido
notas - Lista suas notas
ideias - Lista suas ideias
help - Guia completo de comandos
```

**0.2 — Criar conta no Groq e obter API Key**

- [ ] Acesse `console.groq.com` e crie uma conta gratuita (não precisa de cartão)
- [ ] Vá em **API Keys → Create API Key**
- [ ] Copie a key gerada. **Guarde essa key.**

**0.3 — Descobrir seu user_id do Supabase**

- [ ] Acesse o painel do seu Supabase
- [ ] Vá em **Authentication → Users**
- [ ] Copie o UUID do seu usuário (formato: `xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx`). **Guarde esse UUID.**

**0.4 — Gerar o BOT_API_KEY**

- [ ] No terminal, na pasta do projeto, rode:
```bash
python -c "import secrets; print(secrets.token_hex(32))"
```
- [ ] Copie o resultado. **Guarde essa string.**

**0.5 — Adicionar variáveis ao .env**

- [ ] Abra o arquivo `.env` do projeto e adicione no final:
```env
# Bot Telegram
TELEGRAM_BOT_TOKEN=<cole o token do BotFather aqui>
GROQ_API_KEY=<cole a key do Groq aqui>
BOT_API_KEY=<cole o resultado do secrets.token_hex aqui>
BOT_OWNER_USER_ID=<cole o UUID do Supabase aqui>
JTASKS_INTERNAL_URL=http://localhost:8000
```

---

## FASE 2 — Backend (endpoints do JtasksApp)

### Task 1: Dependências e config.py

**Files:**
- Modify: `requirements.txt`
- Modify: `app/config.py`

- [ ] **Passo 1: Adicionar dependências ao requirements.txt**

Abra `requirements.txt` e adicione ao final:
```
python-telegram-bot==20.7
groq>=0.9.0
httpx>=0.27.0
```

- [ ] **Passo 2: Instalar as dependências**

```bash
pip install python-telegram-bot==20.7 "groq>=0.9.0" "httpx>=0.27.0"
```

Saída esperada: instalação sem erros.

- [ ] **Passo 3: Adicionar variáveis ao config.py**

Abra `app/config.py`. O arquivo atual é:
```python
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


settings = Settings()
```

Substitua pelo seguinte (adiciona bloco Bot no final):
```python
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

    # Bot Telegram
    telegram_bot_token: str = ""
    groq_api_key: str = ""
    bot_api_key: str = ""
    bot_owner_user_id: str = ""
    jtasks_internal_url: str = "http://localhost:8000"


settings = Settings()
```

- [ ] **Passo 4: Commit**

```bash
git add requirements.txt app/config.py
git commit -m "feat(bot): adiciona dependências e variáveis de config do bot Telegram"
```

---

### Task 2: app/routers/bot_api.py — endpoints de tarefas

**Files:**
- Create: `app/routers/bot_api.py`

- [ ] **Passo 1: Criar o arquivo app/routers/bot_api.py**

Crie o arquivo com o seguinte conteúdo:

```python
from datetime import date, datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, Header, HTTPException, Query
from pydantic import BaseModel

from app.config import settings
from app.services.supabase_client import get_service_client

router = APIRouter(prefix="/bot", tags=["bot"])


# ── Autenticação ─────────────────────────────────────────────────────────────

def verify_bot_key(x_bot_key: str = Header(...)):
    if x_bot_key != settings.bot_api_key:
        raise HTTPException(status_code=403, detail="Forbidden")


def _client():
    return get_service_client()


def _uid() -> str:
    return settings.bot_owner_user_id


# ── Modelos ──────────────────────────────────────────────────────────────────

class TaskCreate(BaseModel):
    name: str
    project: Optional[str] = None
    priority: str = "normal"
    deadline: Optional[str] = None


class TaskUpdate(BaseModel):
    priority: Optional[str] = None
    deadline: Optional[str] = None


class UpdateCreate(BaseModel):
    text: str


# ── Endpoints de Tarefas ─────────────────────────────────────────────────────

@router.post("/tasks")
def create_task(body: TaskCreate, _: None = Depends(verify_bot_key)):
    client = _client()
    result = client.table("tasks").insert({
        "name": body.name,
        "project": body.project,
        "priority": body.priority,
        "deadline": body.deadline,
        "status": "active",
        "user_id": _uid(),
    }).execute()
    return {"ok": True, "task_id": result.data[0]["id"]}


# IMPORTANTE: /tasks/search deve ser declarado ANTES de /tasks/{task_id}
@router.get("/tasks/search")
def search_tasks(q: str = Query(...), _: None = Depends(verify_bot_key)):
    client = _client()
    result = (
        client.table("tasks")
        .select("id, name, priority, deadline, status")
        .eq("user_id", _uid())
        .eq("status", "active")
        .ilike("name", f"%{q}%")
        .execute()
    )
    return {"tasks": result.data or []}


@router.get("/tasks")
def list_tasks(filter: Optional[str] = Query(None), _: None = Depends(verify_bot_key)):
    client = _client()
    today = date.today().isoformat()
    query = (
        client.table("tasks")
        .select("id, name, priority, deadline, status")
        .eq("user_id", _uid())
        .eq("status", "active")
    )
    if filter == "today":
        query = query.eq("deadline", today)
    elif filter == "overdue":
        query = query.lt("deadline", today).not_.is_("deadline", "null")
    result = query.order("created_at", desc=True).execute()
    return {"tasks": result.data or []}


@router.get("/tasks/{task_id}")
def get_task(task_id: str, _: None = Depends(verify_bot_key)):
    client = _client()
    result = (
        client.table("tasks")
        .select("id, name, priority, deadline, status, project, task_updates(*)")
        .eq("id", task_id)
        .eq("user_id", _uid())
        .single()
        .execute()
    )
    return {"task": result.data}


@router.patch("/tasks/{task_id}")
def update_task(task_id: str, body: TaskUpdate, _: None = Depends(verify_bot_key)):
    updates = {}
    if body.priority is not None:
        updates["priority"] = body.priority
    if body.deadline is not None:
        updates["deadline"] = body.deadline
    if not updates:
        raise HTTPException(status_code=400, detail="Nenhum campo para atualizar")
    _client().table("tasks").update(updates).eq("id", task_id).eq("user_id", _uid()).execute()
    return {"ok": True}


@router.post("/tasks/{task_id}/complete")
def complete_task(task_id: str, _: None = Depends(verify_bot_key)):
    completed_dt = datetime.now(timezone.utc).replace(hour=12, minute=0, second=0).isoformat()
    _client().table("tasks").update({
        "status": "completed",
        "completed_at": completed_dt,
    }).eq("id", task_id).eq("user_id", _uid()).execute()
    return {"ok": True}


@router.post("/tasks/{task_id}/discard")
def discard_task(task_id: str, _: None = Depends(verify_bot_key)):
    _client().table("tasks").update({"status": "discarded"}).eq("id", task_id).eq("user_id", _uid()).execute()
    return {"ok": True}


@router.post("/tasks/{task_id}/updates")
def add_task_update(task_id: str, body: UpdateCreate, _: None = Depends(verify_bot_key)):
    _client().table("task_updates").insert({
        "task_id": task_id,
        "user_id": _uid(),
        "text": body.text,
    }).execute()
    return {"ok": True}
```

- [ ] **Passo 2: Commit parcial**

```bash
git add app/routers/bot_api.py
git commit -m "feat(bot): adiciona endpoints de tarefas no bot_api.py"
```

---

### Task 3: app/routers/bot_api.py — endpoints de notas e ideias

**Files:**
- Modify: `app/routers/bot_api.py`

- [ ] **Passo 1: Adicionar modelos e endpoints de notas e ideias**

Abra `app/routers/bot_api.py` e adicione ao final do arquivo (após o último endpoint de tarefas):

```python
# ── Modelos de Notas e Ideias ────────────────────────────────────────────────

class NoteCreate(BaseModel):
    content: str


class IdeaCreate(BaseModel):
    title: str
    description: Optional[str] = None
    project: Optional[str] = None


# ── Endpoints de Notas ───────────────────────────────────────────────────────

@router.post("/notes")
def create_note(body: NoteCreate, _: None = Depends(verify_bot_key)):
    client = _client()
    result = client.table("notes").insert({
        "content": body.content,
        "color": "yellow",
        "user_id": _uid(),
    }).execute()
    return {"ok": True, "note_id": result.data[0]["id"]}


# IMPORTANTE: /notes/search deve ser declarado ANTES de /notes/{note_id}
@router.get("/notes/search")
def search_notes(q: str = Query(...), _: None = Depends(verify_bot_key)):
    client = _client()
    result = (
        client.table("notes")
        .select("id, content, created_at")
        .eq("user_id", _uid())
        .ilike("content", f"%{q}%")
        .execute()
    )
    return {"notes": result.data or []}


@router.get("/notes")
def list_notes(_: None = Depends(verify_bot_key)):
    client = _client()
    result = (
        client.table("notes")
        .select("id, content, created_at")
        .eq("user_id", _uid())
        .order("created_at", desc=True)
        .limit(10)
        .execute()
    )
    return {"notes": result.data or []}


@router.delete("/notes/{note_id}")
def delete_note(note_id: str, _: None = Depends(verify_bot_key)):
    _client().table("notes").delete().eq("id", note_id).eq("user_id", _uid()).execute()
    return {"ok": True}


# ── Endpoints de Ideias ──────────────────────────────────────────────────────

@router.post("/ideas")
def create_idea(body: IdeaCreate, _: None = Depends(verify_bot_key)):
    client = _client()
    result = client.table("ideas").insert({
        "title": body.title,
        "description": body.description,
        "project": body.project,
        "potential": "media",
        "user_id": _uid(),
    }).execute()
    return {"ok": True, "idea_id": result.data[0]["id"]}


# IMPORTANTE: /ideas/search deve ser declarado ANTES de /ideas/{idea_id}
@router.get("/ideas/search")
def search_ideas(q: str = Query(...), _: None = Depends(verify_bot_key)):
    client = _client()
    result = (
        client.table("ideas")
        .select("id, title, description, project")
        .eq("user_id", _uid())
        .ilike("title", f"%{q}%")
        .execute()
    )
    return {"ideas": result.data or []}


@router.get("/ideas")
def list_ideas(_: None = Depends(verify_bot_key)):
    client = _client()
    result = (
        client.table("ideas")
        .select("id, title, description, project, created_at")
        .eq("user_id", _uid())
        .order("created_at", desc=True)
        .limit(10)
        .execute()
    )
    return {"ideas": result.data or []}


@router.delete("/ideas/{idea_id}")
def delete_idea(idea_id: str, _: None = Depends(verify_bot_key)):
    _client().table("ideas").delete().eq("id", idea_id).eq("user_id", _uid()).execute()
    return {"ok": True}
```

- [ ] **Passo 2: Commit**

```bash
git add app/routers/bot_api.py
git commit -m "feat(bot): adiciona endpoints de notas e ideias no bot_api.py"
```

---

### Task 4: Registrar router em main.py e verificar endpoints

**Files:**
- Modify: `main.py`

- [ ] **Passo 1: Registrar o router do bot em main.py**

Abra `main.py`. Localize a linha de imports dos routers:
```python
from app.routers import auth, app_router, tasks, projects, presets, performance, notify, export, ideas, notes, user
```

Substitua por:
```python
from app.routers import auth, app_router, tasks, projects, presets, performance, notify, export, ideas, notes, user, bot_api
```

Depois, localize o bloco de `app.include_router(...)` e adicione ao final:
```python
app.include_router(bot_api.router)
```

- [ ] **Passo 2: Iniciar o servidor localmente**

```bash
python main.py
```

Saída esperada: servidor rodando em `http://localhost:8000` sem erros.

- [ ] **Passo 3: Testar os endpoints manualmente**

Em outro terminal, substitua `<SUA_BOT_API_KEY>` pela key que você gerou e rode:

```bash
# Criar uma tarefa de teste
curl -X POST http://localhost:8000/bot/tasks \
  -H "X-Bot-Key: <SUA_BOT_API_KEY>" \
  -H "Content-Type: application/json" \
  -d '{"name": "Tarefa de teste do bot", "priority": "urgente"}'
```

Saída esperada:
```json
{"ok": true, "task_id": "algum-uuid-aqui"}
```

```bash
# Listar tarefas ativas
curl http://localhost:8000/bot/tasks \
  -H "X-Bot-Key: <SUA_BOT_API_KEY>"
```

Saída esperada: `{"tasks": [...]}` com a tarefa criada.

```bash
# Testar autenticação inválida
curl http://localhost:8000/bot/tasks \
  -H "X-Bot-Key: chave-errada"
```

Saída esperada: `{"detail": "Forbidden"}` com status 403.

- [ ] **Passo 4: Commit**

```bash
git add main.py
git commit -m "feat(bot): registra router bot_api no FastAPI"
```

---

## FASE 3 — Bot Telegram

### Task 5: bot/prompts.py

**Files:**
- Create: `bot/__init__.py`
- Create: `bot/prompts.py`

- [ ] **Passo 1: Criar bot/__init__.py**

Crie o arquivo `bot/__init__.py` vazio:
```bash
echo "" > bot/__init__.py
```

- [ ] **Passo 2: Criar bot/prompts.py**

```python
from datetime import date


SYSTEM_PROMPT = """Você é um assistente do JtasksApp. Interprete a mensagem do usuário e retorne APENAS um JSON com a estrutura abaixo, sem texto adicional, sem markdown.

{{
  "action": "<ação>",
  "confidence": "high ou low",
  "data": {{
    "name": null,
    "priority": "normal",
    "deadline": null,
    "project": null,
    "content": null,
    "title": null,
    "description": null,
    "update_text": null,
    "filter": null,
    "search_term": null
  }},
  "clarification_needed": null
}}

Ações disponíveis:
- create_task: criar uma tarefa
- create_note: criar uma nota (padrão quando o usuário não especifica nota ou ideia)
- create_idea: criar uma ideia (somente quando o usuário diz explicitamente "ideia")
- list_tasks: listar tarefas (data.filter: "active", "today" ou "overdue")
- list_notes: listar notas
- list_ideas: listar ideias
- get_task: ver detalhes de uma tarefa
- complete_task: marcar tarefa como concluída
- discard_task: descartar tarefa
- update_priority: mudar prioridade (data.priority e data.search_term)
- update_deadline: atualizar prazo (data.deadline e data.search_term)
- add_update: adicionar atualização (data.update_text e data.search_term)
- delete_note: deletar nota (data.search_term com trecho do conteúdo)
- delete_idea: deletar ideia (data.search_term com trecho do título)
- unknown: quando não entender a intenção

Regras:
- Hoje é {today}
- Prioridades válidas: "critica", "urgente", "normal" (padrão: "normal")
- Palavras "urgente", "importante" → priority: "urgente"
- Palavras "crítico", "crítica" → priority: "critica"
- Prazos relativos ("amanhã", "sexta-feira", "próxima semana") → converta para YYYY-MM-DD usando a data de hoje como referência
- Se a intenção for clara e todos os dados necessários estiverem presentes → confidence: "high"
- Se faltar algum dado essencial ou a intenção for ambígua → confidence: "low" e preencha clarification_needed com uma pergunta clara
- Para ações de gestão (concluir, atualizar, etc): coloque o nome mencionado em data.search_term
- Para create_task: coloque o nome em data.name
- Para create_note: coloque o conteúdo em data.content
- Para create_idea: coloque o título em data.title
- Retorne SOMENTE o JSON. Nenhum texto antes ou depois."""


def get_system_prompt() -> str:
    return SYSTEM_PROMPT.format(today=date.today().isoformat())
```

- [ ] **Passo 3: Commit**

```bash
git add bot/__init__.py bot/prompts.py
git commit -m "feat(bot): adiciona prompt do sistema para o LLaMA"
```

---

### Task 6: bot/groq_client.py

**Files:**
- Create: `bot/groq_client.py`

- [ ] **Passo 1: Criar bot/groq_client.py**

```python
import json
import os
import tempfile
import logging

from groq import Groq

from bot.prompts import get_system_prompt

logger = logging.getLogger(__name__)

_groq_client = None


def _get_client() -> Groq:
    global _groq_client
    if _groq_client is None:
        _groq_client = Groq(api_key=os.environ["GROQ_API_KEY"])
    return _groq_client


def transcribe_audio(audio_bytes: bytes) -> str:
    """Transcreve áudio OGG usando Groq Whisper. Retorna string vazia se falhar."""
    client = _get_client()
    with tempfile.NamedTemporaryFile(suffix=".ogg", delete=False) as f:
        f.write(audio_bytes)
        temp_path = f.name
    try:
        with open(temp_path, "rb") as audio_file:
            result = client.audio.transcriptions.create(
                file=("audio.ogg", audio_file, "audio/ogg"),
                model="whisper-large-v3",
                language="pt",
            )
        return result.text.strip()
    except Exception as e:
        logger.error(f"Erro ao transcrever áudio: {e}")
        return ""
    finally:
        os.unlink(temp_path)


def interpret_text(text: str) -> dict:
    """Interpreta o texto com LLaMA e retorna o dict de ação."""
    client = _get_client()
    response = client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=[
            {"role": "system", "content": get_system_prompt()},
            {"role": "user", "content": text},
        ],
        temperature=0.1,
        max_tokens=512,
    )
    content = response.choices[0].message.content.strip()

    # Remove blocos markdown caso o modelo os inclua
    if content.startswith("```"):
        parts = content.split("```")
        content = parts[1]
        if content.startswith("json"):
            content = content[4:]
        content = content.strip()

    return json.loads(content)
```

- [ ] **Passo 2: Commit**

```bash
git add bot/groq_client.py
git commit -m "feat(bot): adiciona groq_client com STT Whisper e NLP LLaMA"
```

---

### Task 7: bot/formatters.py

**Files:**
- Create: `bot/formatters.py`

- [ ] **Passo 1: Criar bot/formatters.py**

```python
from typing import Optional

PRIORITY_EMOJI = {"critica": "🔴", "urgente": "🟠", "normal": "⚪"}
PRIORITY_LABEL = {"critica": "crítica", "urgente": "urgente", "normal": "normal"}


def format_task_list(tasks: list, title: str) -> str:
    if not tasks:
        return f"📋 {title}: nenhuma tarefa encontrada."
    lines = [f"📋 *{title}* ({len(tasks)}):"]
    for t in tasks:
        emoji = PRIORITY_EMOJI.get(t.get("priority", "normal"), "⚪")
        name = t.get("name", "")
        deadline = t.get("deadline", "")
        deadline_str = f" — {deadline}" if deadline else ""
        lines.append(f"{emoji} {name}{deadline_str}")
    return "\n".join(lines)


def format_task_detail(task: dict) -> str:
    priority = task.get("priority", "normal")
    emoji = PRIORITY_EMOJI.get(priority, "⚪")
    lines = [
        f"📌 *{task.get('name', '')}*",
        f"Prioridade: {emoji} {PRIORITY_LABEL.get(priority, priority)}",
    ]
    if task.get("project"):
        lines.append(f"Projeto: {task['project']}")
    if task.get("deadline"):
        lines.append(f"Prazo: {task['deadline']}")
    updates = task.get("task_updates") or []
    if updates:
        sorted_updates = sorted(updates, key=lambda x: x.get("created_at", ""), reverse=True)
        lines.append(f"\n📝 *Updates ({len(updates)}):*")
        for u in sorted_updates[:3]:
            lines.append(f"• {u['text']}")
    return "\n".join(lines)


def format_note_list(notes: list) -> str:
    if not notes:
        return "📝 Nenhuma nota encontrada."
    lines = [f"📝 *Notas ({len(notes)}):*"]
    for n in notes:
        content = n.get("content", "")
        preview = content[:60] + "..." if len(content) > 60 else content
        lines.append(f"• {preview}")
    return "\n".join(lines)


def format_idea_list(ideas: list) -> str:
    if not ideas:
        return "💡 Nenhuma ideia encontrada."
    lines = [f"💡 *Ideias ({len(ideas)}):*"]
    for i in ideas:
        title = i.get("title", "")
        project = f" [{i['project']}]" if i.get("project") else ""
        lines.append(f"• {title}{project}")
    return "\n".join(lines)


def format_task_created(name: str, priority: str, deadline: Optional[str]) -> str:
    emoji = PRIORITY_EMOJI.get(priority, "⚪")
    deadline_str = f" | Prazo: {deadline}" if deadline else ""
    return f"✅ Tarefa criada: *{name}*\nPrioridade: {emoji} {PRIORITY_LABEL.get(priority, priority)}{deadline_str}"


def format_task_completed(name: str) -> str:
    return f"✅ Tarefa *{name}* marcada como concluída."


def format_task_discarded(name: str) -> str:
    return f"🗑️ Tarefa *{name}* descartada."


def format_task_updated(name: str, field: str, value: str) -> str:
    return f"✅ *{name}* atualizada: {field} → {value}"


def format_update_added(task_name: str) -> str:
    return f"✅ Update adicionado à tarefa *{task_name}*."


def format_note_created() -> str:
    return "✅ Nota criada."


def format_idea_created(title: str) -> str:
    return f"💡 Ideia registrada: *{title}*."
```

- [ ] **Passo 2: Commit**

```bash
git add bot/formatters.py
git commit -m "feat(bot): adiciona formatters para respostas do bot"
```

---

### Task 8: bot/actions.py

**Files:**
- Create: `bot/actions.py`

- [ ] **Passo 1: Criar bot/actions.py**

```python
import os
from typing import Optional

import httpx


def _base_url() -> str:
    return os.environ.get("JTASKS_INTERNAL_URL", "http://localhost:8000")


def _headers() -> dict:
    return {"X-Bot-Key": os.environ["BOT_API_KEY"]}


def _get(path: str, params: dict = None) -> dict:
    r = httpx.get(f"{_base_url()}{path}", headers=_headers(), params=params, timeout=10)
    r.raise_for_status()
    return r.json()


def _post(path: str, body: dict = None) -> dict:
    r = httpx.post(f"{_base_url()}{path}", headers=_headers(), json=body or {}, timeout=10)
    r.raise_for_status()
    return r.json()


def _patch(path: str, body: dict) -> dict:
    r = httpx.patch(f"{_base_url()}{path}", headers=_headers(), json=body, timeout=10)
    r.raise_for_status()
    return r.json()


def _delete(path: str) -> dict:
    r = httpx.delete(f"{_base_url()}{path}", headers=_headers(), timeout=10)
    r.raise_for_status()
    return r.json()


# ── Tarefas ──────────────────────────────────────────────────────────────────

def create_task(name: str, project: Optional[str], priority: str, deadline: Optional[str]) -> dict:
    return _post("/bot/tasks", {
        "name": name, "project": project, "priority": priority, "deadline": deadline
    })


def list_tasks(filter: Optional[str] = None) -> list:
    params = {"filter": filter} if filter else {}
    return _get("/bot/tasks", params).get("tasks", [])


def search_tasks(q: str) -> list:
    return _get("/bot/tasks/search", {"q": q}).get("tasks", [])


def get_task(task_id: str) -> dict:
    return _get(f"/bot/tasks/{task_id}").get("task", {})


def complete_task(task_id: str) -> dict:
    return _post(f"/bot/tasks/{task_id}/complete")


def discard_task(task_id: str) -> dict:
    return _post(f"/bot/tasks/{task_id}/discard")


def update_task(task_id: str, priority: Optional[str] = None, deadline: Optional[str] = None) -> dict:
    body = {}
    if priority:
        body["priority"] = priority
    if deadline:
        body["deadline"] = deadline
    return _patch(f"/bot/tasks/{task_id}", body)


def add_task_update(task_id: str, text: str) -> dict:
    return _post(f"/bot/tasks/{task_id}/updates", {"text": text})


# ── Notas ────────────────────────────────────────────────────────────────────

def create_note(content: str) -> dict:
    return _post("/bot/notes", {"content": content})


def list_notes() -> list:
    return _get("/bot/notes").get("notes", [])


def search_notes(q: str) -> list:
    return _get("/bot/notes/search", {"q": q}).get("notes", [])


def delete_note(note_id: str) -> dict:
    return _delete(f"/bot/notes/{note_id}")


# ── Ideias ───────────────────────────────────────────────────────────────────

def create_idea(title: str, description: Optional[str], project: Optional[str]) -> dict:
    return _post("/bot/ideas", {"title": title, "description": description, "project": project})


def list_ideas() -> list:
    return _get("/bot/ideas").get("ideas", [])


def search_ideas(q: str) -> list:
    return _get("/bot/ideas/search", {"q": q}).get("ideas", [])


def delete_idea(idea_id: str) -> dict:
    return _delete(f"/bot/ideas/{idea_id}")
```

- [ ] **Passo 2: Commit**

```bash
git add bot/actions.py
git commit -m "feat(bot): adiciona actions com chamadas HTTP ao JtasksApp"
```

---

### Task 9: bot/bot.py

**Files:**
- Create: `bot/bot.py`

- [ ] **Passo 1: Criar bot/bot.py**

```python
import logging
import os
import time
from typing import Optional

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import (
    Application,
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

from bot import actions, formatters, groq_client

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)

# Estado de ações pendentes por chat_id
# Estrutura: {chat_id: {"action": str, "data": dict, "items": list, "ts": float}}
_pending: dict = {}
PENDING_TTL = 60  # segundos


HELP_TEXT = """🤖 *JtasksApp Bot*

*Capture rápido:*
• "Cria tarefa urgente: reunião com cliente amanhã"
• "Anota: lembrar de enviar o contrato"
• "Ideia: novo dashboard de métricas"

*Gerenciar tarefas:*
• "Quais minhas tarefas?" / "O que tenho pra hoje?"
• "Quais estão atrasadas?"
• "Me mostra a tarefa reunião com cliente"
• "Concluí a reunião com cliente"
• "Descarta a tarefa X"
• "Muda a prioridade da reunião pra crítica"
• "Muda o prazo da reunião pra sexta"
• "Adiciona update na reunião: cliente confirmou"

*Notas e ideias:*
• "Minhas notas" / "Minhas ideias"
• "Deleta aquela nota sobre o contrato"
• "Deleta a ideia do dashboard"

💡 Fale ou escreva naturalmente — não precisa de comandos exatos."""


def _clear_expired_pending(chat_id: int):
    """Remove ação pendente se passou do TTL."""
    state = _pending.get(chat_id)
    if state and time.time() - state.get("ts", 0) > PENDING_TTL:
        _pending.pop(chat_id, None)


async def _process_text(text: str, update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Interpreta o texto com LLM e executa a ação correspondente."""
    chat_id = update.effective_chat.id
    _clear_expired_pending(chat_id)

    try:
        result = groq_client.interpret_text(text)
    except Exception as e:
        logger.error(f"Erro LLM: {e}")
        await update.message.reply_text(
            "Serviço de IA indisponível no momento. Tente em instantes."
        )
        return

    action = result.get("action", "unknown")
    confidence = result.get("confidence", "low")
    data = result.get("data", {})
    clarification = result.get("clarification_needed")

    if action == "unknown":
        await update.message.reply_text(
            "Não entendi. Digite /help para ver o que posso fazer."
        )
        return

    if confidence == "low":
        await update.message.reply_text(
            clarification or "Não entendi completamente. Pode reformular?"
        )
        return

    await _execute_action(action, data, update.message.reply_text)


async def _execute_action(action: str, data: dict, reply, chat_id: Optional[int] = None):
    """Executa a ação interpretada pelo LLM."""
    try:
        # ── Capture ───────────────────────────────────────────────────────────
        if action == "create_task":
            actions.create_task(
                name=data.get("name") or "Nova tarefa",
                project=data.get("project"),
                priority=data.get("priority") or "normal",
                deadline=data.get("deadline"),
            )
            msg = formatters.format_task_created(
                data.get("name") or "Nova tarefa",
                data.get("priority") or "normal",
                data.get("deadline"),
            )
            await reply(msg, parse_mode="Markdown")

        elif action == "create_note":
            actions.create_note(data.get("content") or "")
            await reply(formatters.format_note_created())

        elif action == "create_idea":
            actions.create_idea(
                title=data.get("title") or "Nova ideia",
                description=data.get("description"),
                project=data.get("project"),
            )
            await reply(
                formatters.format_idea_created(data.get("title") or "Nova ideia"),
                parse_mode="Markdown",
            )

        # ── Listagens ─────────────────────────────────────────────────────────
        elif action == "list_tasks":
            filter_val = data.get("filter") or "active"
            title_map = {
                "today": "Tarefas de hoje",
                "overdue": "Tarefas atrasadas",
                "active": "Tarefas ativas",
            }
            tasks = actions.list_tasks(filter=filter_val)
            msg = formatters.format_task_list(tasks, title_map.get(filter_val, "Tarefas"))
            await reply(msg, parse_mode="Markdown")

        elif action == "list_notes":
            notes = actions.list_notes()
            await reply(formatters.format_note_list(notes), parse_mode="Markdown")

        elif action == "list_ideas":
            ideas = actions.list_ideas()
            await reply(formatters.format_idea_list(ideas), parse_mode="Markdown")

        # ── Gestão de tarefas ─────────────────────────────────────────────────
        elif action in (
            "complete_task", "discard_task", "update_priority",
            "update_deadline", "add_update", "get_task",
        ):
            search_term = data.get("search_term") or data.get("name") or ""
            tasks = actions.search_tasks(search_term)
            if not tasks:
                await reply("Não encontrei nenhuma tarefa com esse nome.")
                return
            if len(tasks) == 1:
                await _run_task_action(action, tasks[0], data, reply)
            else:
                if chat_id is not None:
                    _pending[chat_id] = {
                        "action": action, "data": data, "items": tasks, "ts": time.time()
                    }
                keyboard = [
                    [InlineKeyboardButton(t["name"], callback_data=f"task:{t['id']}:{action}")]
                    for t in tasks[:8]
                ]
                keyboard.append([InlineKeyboardButton("❌ Cancelar", callback_data="cancel")])
                await reply("Qual tarefa?", reply_markup=InlineKeyboardMarkup(keyboard))

        # ── Gestão de notas/ideias ────────────────────────────────────────────
        elif action in ("delete_note", "delete_idea"):
            is_note = action == "delete_note"
            search_term = data.get("search_term") or data.get("content") or data.get("title") or ""
            item_type = "nota" if is_note else "ideia"
            items = actions.search_notes(search_term) if is_note else actions.search_ideas(search_term)
            if not items:
                await reply(f"Não encontrei nenhuma {item_type} com esse nome.")
                return
            if len(items) == 1:
                await _run_delete_action(action, items[0], reply)
            else:
                if chat_id is not None:
                    _pending[chat_id] = {
                        "action": action, "data": data, "items": items, "ts": time.time()
                    }
                name_field = "content" if is_note else "title"
                keyboard = [
                    [InlineKeyboardButton(
                        item[name_field][:40],
                        callback_data=f"item:{item['id']}:{action}"
                    )]
                    for item in items[:8]
                ]
                keyboard.append([InlineKeyboardButton("❌ Cancelar", callback_data="cancel")])
                await reply(f"Qual {item_type}?", reply_markup=InlineKeyboardMarkup(keyboard))

    except Exception as e:
        logger.error(f"Erro ao executar ação '{action}': {e}")
        await reply("Não consegui executar. Tente novamente.")


async def _run_task_action(action: str, task: dict, data: dict, reply):
    task_id = task["id"]
    task_name = task["name"]

    if action == "complete_task":
        actions.complete_task(task_id)
        await reply(formatters.format_task_completed(task_name), parse_mode="Markdown")
    elif action == "discard_task":
        actions.discard_task(task_id)
        await reply(formatters.format_task_discarded(task_name), parse_mode="Markdown")
    elif action == "update_priority":
        priority = data.get("priority") or "normal"
        actions.update_task(task_id, priority=priority)
        await reply(
            formatters.format_task_updated(task_name, "prioridade", priority),
            parse_mode="Markdown",
        )
    elif action == "update_deadline":
        deadline = data.get("deadline")
        actions.update_task(task_id, deadline=deadline)
        await reply(
            formatters.format_task_updated(task_name, "prazo", deadline or "removido"),
            parse_mode="Markdown",
        )
    elif action == "add_update":
        text = data.get("update_text") or ""
        actions.add_task_update(task_id, text)
        await reply(formatters.format_update_added(task_name), parse_mode="Markdown")
    elif action == "get_task":
        task_detail = actions.get_task(task_id)
        await reply(formatters.format_task_detail(task_detail), parse_mode="Markdown")


async def _run_delete_action(action: str, item: dict, reply):
    if action == "delete_note":
        actions.delete_note(item["id"])
        preview = item.get("content", "")[:40]
        await reply(f"🗑️ Nota removida: *{preview}*", parse_mode="Markdown")
    elif action == "delete_idea":
        actions.delete_idea(item["id"])
        await reply(
            f"🗑️ Ideia *{item.get('title', '')}* removida.", parse_mode="Markdown"
        )


# ── Handlers de Mensagens ────────────────────────────────────────────────────

async def handle_voice(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        voice = update.message.voice
        tg_file = await context.bot.get_file(voice.file_id)
        audio_bytes = bytes(await tg_file.download_as_bytearray())
        text = groq_client.transcribe_audio(audio_bytes)
        if not text:
            await update.message.reply_text(
                "Não consegui entender o áudio. Pode repetir com mais clareza?"
            )
            return
        await update.message.reply_text(f'🎙️ Entendi: "{text}"')
        await _process_text(text, update, context)
    except Exception as e:
        logger.error(f"Erro ao processar voz: {e}")
        await update.message.reply_text("Erro ao processar o áudio. Tente novamente.")


async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = (update.message.text or "").strip()
    if not text:
        return
    chat_id = update.effective_chat.id
    await _process_text(text, update, context)


async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    chat_id = query.message.chat.id

    if query.data == "cancel":
        _pending.pop(chat_id, None)
        await query.edit_message_text("Cancelado.")
        return

    _clear_expired_pending(chat_id)
    pending = _pending.pop(chat_id, None)
    if not pending:
        await query.edit_message_text("Ação expirada. Tente novamente.")
        return

    parts = query.data.split(":", 2)
    if len(parts) != 3:
        await query.edit_message_text("Dados inválidos. Tente novamente.")
        return

    prefix, item_id, action = parts
    items = pending.get("items", [])
    item = next((i for i in items if i["id"] == item_id), None)
    if not item:
        await query.edit_message_text("Item não encontrado. Tente novamente.")
        return

    await query.edit_message_text("Processando...")

    async def reply(text, **kwargs):
        await query.message.reply_text(text, **kwargs)

    try:
        if prefix == "task":
            await _run_task_action(action, item, pending.get("data", {}), reply)
        elif prefix == "item":
            await _run_delete_action(action, item, reply)
    except Exception as e:
        logger.error(f"Erro no callback: {e}")
        await reply("Não consegui executar. Tente novamente.")


# ── Comandos ─────────────────────────────────────────────────────────────────

async def cmd_tarefas(update: Update, context: ContextTypes.DEFAULT_TYPE):
    tasks = actions.list_tasks(filter="active")
    await update.message.reply_text(
        formatters.format_task_list(tasks, "Tarefas ativas"), parse_mode="Markdown"
    )


async def cmd_hoje(update: Update, context: ContextTypes.DEFAULT_TYPE):
    tasks = actions.list_tasks(filter="today")
    await update.message.reply_text(
        formatters.format_task_list(tasks, "Tarefas de hoje"), parse_mode="Markdown"
    )


async def cmd_atrasadas(update: Update, context: ContextTypes.DEFAULT_TYPE):
    tasks = actions.list_tasks(filter="overdue")
    await update.message.reply_text(
        formatters.format_task_list(tasks, "Tarefas atrasadas"), parse_mode="Markdown"
    )


async def cmd_notas(update: Update, context: ContextTypes.DEFAULT_TYPE):
    notes = actions.list_notes()
    await update.message.reply_text(formatters.format_note_list(notes), parse_mode="Markdown")


async def cmd_ideias(update: Update, context: ContextTypes.DEFAULT_TYPE):
    ideas = actions.list_ideas()
    await update.message.reply_text(formatters.format_idea_list(ideas), parse_mode="Markdown")


async def cmd_help(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(HELP_TEXT, parse_mode="Markdown")


# ── Entry Point ──────────────────────────────────────────────────────────────

def main():
    token = os.environ["TELEGRAM_BOT_TOKEN"]
    app = Application.builder().token(token).build()

    app.add_handler(CommandHandler("tarefas", cmd_tarefas))
    app.add_handler(CommandHandler("hoje", cmd_hoje))
    app.add_handler(CommandHandler("atrasadas", cmd_atrasadas))
    app.add_handler(CommandHandler("notas", cmd_notas))
    app.add_handler(CommandHandler("ideias", cmd_ideias))
    app.add_handler(CommandHandler("help", cmd_help))
    app.add_handler(CommandHandler("start", cmd_help))
    app.add_handler(MessageHandler(filters.VOICE, handle_voice))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))
    app.add_handler(CallbackQueryHandler(handle_callback))

    logger.info("Bot iniciado em modo polling...")
    app.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    main()
```

- [ ] **Passo 2: Commit**

```bash
git add bot/bot.py
git commit -m "feat(bot): implementa bot.py com handlers, comandos e botões inline"
```

---

### Task 10: Teste local completo

> ⚠️ Esta task envolve passos manuais seus.

**Files:** nenhum — apenas testes.

- [ ] **Passo 1: Garantir que o JtasksApp está rodando**

Em um terminal:
```bash
python main.py
```

- [ ] **Passo 2: Iniciar o bot em outro terminal**

```bash
python bot/bot.py
```

Saída esperada:
```
INFO - Bot iniciado em modo polling...
```

- [ ] **Passo 3: Testar capture de tarefa por texto**

No Telegram, envie ao seu bot:
```
cria tarefa urgente: reunião com cliente amanhã
```

Resposta esperada:
```
✅ Tarefa criada: *Reunião com cliente*
Prioridade: 🟠 urgente | Prazo: 2026-04-12
```

Verifique se a tarefa aparece no JtasksApp.

- [ ] **Passo 4: Testar comando /hoje**

Envie `/hoje` no Telegram.

Resposta esperada: lista das tarefas com prazo para hoje (incluindo a que acabou de criar).

- [ ] **Passo 5: Testar capture de nota**

Envie:
```
anota: lembrar de enviar o relatório mensal
```

Resposta esperada: `✅ Nota criada.`

Verifique se a nota aparece no JtasksApp.

- [ ] **Passo 6: Testar desambiguação com botão inline**

Crie duas tarefas com nomes parecidos via app (ex: "Reunião interna" e "Reunião com cliente").

Depois envie:
```
conclui a tarefa reunião
```

Resposta esperada: mensagem com dois botões — `Reunião interna` e `Reunião com cliente`. Toque num deles e verifique se a tarefa foi concluída.

- [ ] **Passo 7: Testar áudio (voz)**

Grave um áudio no Telegram dizendo:
```
"Cria uma tarefa normal: revisar o contrato"
```

Resposta esperada: bot mostra o texto transcrito e cria a tarefa.

- [ ] **Passo 8: Testar /help**

Envie `/help`. Verifique se o guia aparece formatado.

- [ ] **Passo 9: Commit final da fase local**

```bash
git add .
git commit -m "feat(bot): bot Telegram funcionando localmente"
```

---

## FASE 4 — Deploy no VPS

### Task 11: Configurar systemd no VPS

> ⚠️ Esta task é executada no VPS via SSH, não na máquina local.

**Files:**
- Create: `/etc/systemd/system/jtasks-bot.service` (no VPS)

- [ ] **Passo 1: Fazer push do código**

Na máquina local:
```bash
git push origin master
```

- [ ] **Passo 2: Conectar ao VPS e atualizar o código**

```bash
ssh seu-usuario@seu-vps
cd /caminho/para/JtasksApp
git fetch origin master
git reset --hard origin/master
pip install -r requirements.txt
```

- [ ] **Passo 3: Adicionar as variáveis do bot ao .env do VPS**

```bash
nano .env
```

Adicione ao final (com os valores reais):
```env
TELEGRAM_BOT_TOKEN=seu_token_aqui
GROQ_API_KEY=sua_groq_key_aqui
BOT_API_KEY=sua_bot_api_key_aqui
BOT_OWNER_USER_ID=seu_uuid_supabase_aqui
JTASKS_INTERNAL_URL=http://localhost:8080
```

> Atenção: `JTASKS_INTERNAL_URL` deve usar a porta que o JtasksApp usa no VPS (verifique em `.env` a variável `PORT`).

- [ ] **Passo 4: Descobrir os caminhos corretos**

```bash
which python
# ou
which python3
pwd
```

Anote os dois caminhos — você vai precisar deles no próximo passo.

- [ ] **Passo 5: Criar o arquivo de serviço systemd**

```bash
sudo nano /etc/systemd/system/jtasks-bot.service
```

Cole o conteúdo abaixo, substituindo `/CAMINHO/PARA/VENV/python` e `/CAMINHO/PARA/JtasksApp` pelos caminhos reais do VPS:

```ini
[Unit]
Description=JtasksApp Telegram Bot
After=network.target jtasks.service

[Service]
WorkingDirectory=/CAMINHO/PARA/JtasksApp
ExecStart=/CAMINHO/PARA/VENV/python bot/bot.py
Restart=always
RestartSec=5
EnvironmentFile=/CAMINHO/PARA/JtasksApp/.env
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
```

- [ ] **Passo 6: Ativar e iniciar o serviço**

```bash
sudo systemctl daemon-reload
sudo systemctl enable jtasks-bot
sudo systemctl start jtasks-bot
sudo systemctl status jtasks-bot
```

Saída esperada: `Active: active (running)`.

- [ ] **Passo 7: Verificar logs do bot**

```bash
sudo journalctl -u jtasks-bot -f
```

Você deve ver:
```
INFO - Bot iniciado em modo polling...
```

- [ ] **Passo 8: Testar no Telegram com bot em produção**

Envie uma mensagem ao bot pelo Telegram e confirme que ele responde normalmente.

- [ ] **Passo 9: Testar resiliência — reiniciar o VPS**

```bash
sudo reboot
```

Após o VPS reiniciar (aguarde ~1 minuto), envie uma mensagem ao bot. O bot deve responder normalmente, confirmando que o systemd reiniciou o processo automaticamente.

---

## Critérios de Sucesso

- [ ] Voz e texto funcionam de forma intercambiável
- [ ] "Cria tarefa urgente: reunião amanhã" → tarefa aparece no JtasksApp sem perguntas adicionais
- [ ] "Conclui a reunião" com duas tarefas parecidas → exibe botões inline para escolha
- [ ] `/tarefas`, `/hoje`, `/atrasadas`, `/notas`, `/ideias` funcionam como atalhos
- [ ] `/help` retorna guia completo formatado
- [ ] Bot continua rodando após reinício do VPS (systemd)
- [ ] Falha no Groq não derruba o JtasksApp (processos isolados)
