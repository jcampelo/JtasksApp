# Theme Sync Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Persistir a preferência de tema (light/dark) no Supabase e carregá-la ao abrir a aplicação, sincronizando entre dispositivos.

**Architecture:** Nova tabela `user_preferences` armazena o tema por usuário. O endpoint `POST /user/theme` salva a preferência via upsert. O `app_router.py` consulta o banco ao carregar `/app` e passa `user_theme` para o template, que aplica o `data-theme` no `<html>` antes do render — eliminando flash de tema.

**Tech Stack:** FastAPI, Supabase (supabase-py), Jinja2, JavaScript (fetch API)

---

## Mapa de Arquivos

| Arquivo | Ação | Responsabilidade |
|---------|------|-----------------|
| Supabase SQL Editor | Executar SQL | Criar tabela `user_preferences` + RLS |
| `app/routers/user.py` | Criar | Endpoint `POST /user/theme` |
| `main.py` | Modificar | Registrar o novo router |
| `app/routers/app_router.py` | Modificar | Buscar tema ao carregar `/app` |
| `app/templates/base.html` | Modificar | Aplicar tema via Jinja2 no `<html>` |
| `app/templates/partials/sidebar.html` | Modificar | Fetch ao trocar tema + atualizar localStorage |

---

## Task 1: Criar tabela `user_preferences` no Supabase

**Files:**
- Executar no Supabase SQL Editor (Dashboard → SQL Editor)

- [ ] **Step 1: Executar o SQL de criação da tabela**

No Supabase Dashboard → SQL Editor, executar:

```sql
CREATE TABLE user_preferences (
  user_id uuid PRIMARY KEY REFERENCES auth.users(id) ON DELETE CASCADE,
  theme   text NOT NULL DEFAULT 'light' CHECK (theme IN ('light', 'dark'))
);

ALTER TABLE user_preferences ENABLE ROW LEVEL SECURITY;

CREATE POLICY "user acessa apenas suas preferencias"
  ON user_preferences
  FOR ALL
  USING (auth.uid() = user_id);
```

- [ ] **Step 2: Verificar a tabela criada**

No Supabase Dashboard → Table Editor, confirmar que `user_preferences` aparece com as colunas `user_id` e `theme`.

---

## Task 2: Criar endpoint `POST /user/theme`

**Files:**
- Create: `app/routers/user.py`
- Modify: `main.py`

- [ ] **Step 1: Criar o arquivo `app/routers/user.py`**

```python
from fastapi import APIRouter, Request, Depends
from fastapi.responses import JSONResponse, RedirectResponse

from app.deps import get_current_user
from app.services.supabase_client import get_user_client

router = APIRouter()


@router.post("/user/theme")
async def save_theme(request: Request, user=Depends(get_current_user)):
    if isinstance(user, RedirectResponse):
        return user

    body = await request.json()
    theme = body.get("theme", "light")
    if theme not in ("light", "dark"):
        return JSONResponse({"ok": False, "error": "invalid theme"}, status_code=400)

    client = get_user_client(user["access_token"], user["refresh_token"])
    client.table("user_preferences").upsert(
        {"user_id": user["user_id"], "theme": theme}
    ).execute()

    return JSONResponse({"ok": True})
```

- [ ] **Step 2: Registrar o router em `main.py`**

Adicionar o import e o `include_router`. O arquivo atual tem:

```python
from app.routers import auth, app_router, tasks, projects, presets, performance, notify, export, ideas, notes
```

Alterar para:

```python
from app.routers import auth, app_router, tasks, projects, presets, performance, notify, export, ideas, notes, user
```

E após os outros `include_router`, adicionar:

```python
app.include_router(user.router)
```

- [ ] **Step 3: Testar o endpoint manualmente**

Com a aplicação rodando (`python main.py`), abrir o terminal e executar:

```bash
# Substitua <TOKEN> pelo access_token de uma sessão ativa (visível em request.session["user"]["access_token"])
curl -X POST http://localhost:8080/user/theme \
  -H "Content-Type: application/json" \
  -d '{"theme": "dark"}' \
  -b "session=<cookie>"
```

Ou testar via navegador: logar na aplicação, abrir Console (F12) e executar:

```javascript
fetch('/user/theme', {
  method: 'POST',
  headers: {'Content-Type': 'application/json'},
  body: JSON.stringify({theme: 'dark'})
}).then(r => r.json()).then(console.log)
```

Expected: `{ok: true}`

Verificar no Supabase → Table Editor → `user_preferences` que a linha foi inserida.

- [ ] **Step 4: Commit**

```bash
git add app/routers/user.py main.py
git commit -m "feat(user): adiciona endpoint POST /user/theme para salvar preferencia de tema"
```

---

## Task 3: Buscar tema ao carregar `/app`

**Files:**
- Modify: `app/routers/app_router.py`

- [ ] **Step 1: Alterar `app_router.py` para buscar o tema do banco**

O arquivo atual (`app/routers/app_router.py`) tem o endpoint `/app` assim:

```python
@router.get("/app", response_class=HTMLResponse)
async def app_page(request: Request, user=Depends(get_current_user)):
    if isinstance(user, RedirectResponse):
        return user
    return templates.TemplateResponse(
        "pages/app.html",
        {"request": request, "user": user, "css_version": _CSS_V},
    )
```

Substituir por:

```python
from app.services.supabase_client import get_user_client

@router.get("/app", response_class=HTMLResponse)
async def app_page(request: Request, user=Depends(get_current_user)):
    if isinstance(user, RedirectResponse):
        return user

    client = get_user_client(user["access_token"], user["refresh_token"])
    prefs = client.table("user_preferences") \
        .select("theme") \
        .eq("user_id", user["user_id"]) \
        .execute()
    user_theme = prefs.data[0]["theme"] if prefs.data else "light"

    return templates.TemplateResponse(
        "pages/app.html",
        {"request": request, "user": user, "css_version": _CSS_V, "user_theme": user_theme},
    )
```

Adicionar o import de `get_user_client` no topo do arquivo (se ainda não estiver):

```python
from app.services.supabase_client import get_user_client
```

- [ ] **Step 2: Verificar que a aplicação ainda sobe sem erros**

```bash
python main.py
```

Expected: `Application startup complete.` sem erros.

- [ ] **Step 3: Commit**

```bash
git add app/routers/app_router.py
git commit -m "feat(app): busca tema do usuario no banco ao carregar /app"
```

---

## Task 4: Aplicar tema via Jinja2 no `base.html`

**Files:**
- Modify: `app/templates/base.html`

- [ ] **Step 1: Alterar a tag `<html>` para aplicar o tema do servidor**

No `base.html`, a linha atual é:

```html
<html lang="pt-BR">
```

Substituir por:

```html
<html lang="pt-BR" {% if user_theme == 'dark' %}data-theme="dark"{% endif %}>
```

- [ ] **Step 2: Remover o bloco JavaScript de tema do `<head>`**

O `base.html` atual tem este bloco no `<head>` (linhas 12-17):

```html
<script>
  (function() {
    var t = localStorage.getItem("jtasks-theme");
    if (t === "dark") document.documentElement.setAttribute("data-theme", "dark");
  })();
</script>
```

**Remover este bloco inteiro.** O tema agora vem do servidor via Jinja2. O `localStorage` continuará sendo usado apenas pelo toggle para resposta imediata.

> **Atenção:** A página de login (`login.html`) não recebe `user_theme`. Verificar se ela herda `base.html` e usa `data-theme`. Se sim, o `{% if user_theme %}` protege contra `UndefinedError` pois a variável simplesmente não estará definida e o `<html>` ficará sem `data-theme` — comportamento correto para a tela de login.

- [ ] **Step 3: Verificar que a página de login não quebrou**

Acessar `http://localhost:8080/auth/login`. A página deve carregar sem erros. O tema escuro não deve ser aplicado na tela de login (comportamento esperado).

- [ ] **Step 4: Verificar que o tema é aplicado corretamente ao logar**

1. Salvar tema `dark` manualmente via console (Task 2, Step 3)
2. Recarregar `http://localhost:8080/app`
3. Inspecionar o elemento `<html>` — deve ter `data-theme="dark"` desde o render inicial, sem flash

- [ ] **Step 5: Commit**

```bash
git add app/templates/base.html
git commit -m "feat(ui): aplica tema via Jinja2 no render inicial eliminando flash de tema"
```

---

## Task 5: Salvar tema no banco ao trocar via toggle

**Files:**
- Modify: `app/templates/partials/sidebar.html`

- [ ] **Step 1: Adicionar fetch ao toggle de tema no `sidebar.html`**

No `sidebar.html`, o botão de tema atual (aproximadamente linha 131) contém um `onclick` com esta lógica:

```javascript
onclick="(function(){
  var dark = document.documentElement.getAttribute('data-theme')==='dark';
  document.documentElement.setAttribute('data-theme', dark ? 'light' : 'dark');
  localStorage.setItem('jtasks-theme', dark ? 'light' : 'dark');
  updateThemeIcon();
  if (document.querySelector('.nav-item.active[data-tab=performance]')) {
    loadPerformance();
  }
}).call(this)"
```

Substituir por:

```javascript
onclick="(function(){
  var dark = document.documentElement.getAttribute('data-theme')==='dark';
  var newTheme = dark ? 'light' : 'dark';
  document.documentElement.setAttribute('data-theme', newTheme);
  localStorage.setItem('jtasks-theme', newTheme);
  updateThemeIcon();
  if (document.querySelector('.nav-item.active[data-tab=performance]')) {
    loadPerformance();
  }
  fetch('/user/theme', {
    method: 'POST',
    headers: {'Content-Type': 'application/json'},
    body: JSON.stringify({theme: newTheme})
  });
}).call(this)"
```

- [ ] **Step 2: Testar o fluxo completo**

1. Abrir `http://localhost:8080/app` no navegador A (desktop)
2. Trocar o tema para dark
3. Verificar no Supabase → `user_preferences` que o registro foi atualizado para `dark`
4. Abrir `http://localhost:8080/app` em outro navegador/aba (modo privado simula outro dispositivo)
5. Confirmar que o tema dark é aplicado desde o carregamento inicial, sem flash

- [ ] **Step 3: Commit**

```bash
git add app/templates/partials/sidebar.html
git commit -m "feat(ui): persiste preferencia de tema no banco ao trocar via toggle"
```

---

## Verificação Final

- [ ] Trocar tema no desktop → verificar no Supabase que `user_preferences` foi atualizado
- [ ] Abrir em modo privado → tema correto aplicado sem flash desde o primeiro render
- [ ] Página de login não quebrou (sem `UndefinedError` do Jinja2)
- [ ] Tema `light` (padrão) funciona para usuários sem registro em `user_preferences`
