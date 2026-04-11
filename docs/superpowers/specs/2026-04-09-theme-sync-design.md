# Design: Sincronização de Tema entre Dispositivos

**Data:** 2026-04-09  
**Status:** Aprovado

---

## Objetivo

Persistir a preferência de tema (light/dark) do usuário no Supabase, sincronizando-a entre dispositivos ao carregar a aplicação. A troca de tema em um dispositivo deve refletir no próximo acesso de qualquer outro dispositivo.

---

## Comportamento Esperado

- Usuário troca o tema no desktop → salva no banco
- Usuário abre a aplicação no mobile → tema já vem correto, sem flash
- Não há sincronização em tempo real (sem WebSocket); o tema é carregado apenas no acesso inicial

---

## Banco de Dados

Nova tabela `user_preferences` no Supabase:

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

**Upsert:** ao salvar, usar upsert (insert or update) para evitar duplicatas.

---

## Backend

### Novo endpoint

```
POST /user/theme
Body: { "theme": "dark" | "light" }
```

- Requer autenticação via `Depends(get_current_user)`
- Faz upsert na tabela `user_preferences`
- Retorna `200 OK` com `{"ok": true}`

### Alteração em `app_router.py`

Ao renderizar `/app`, buscar o tema salvo do banco:

```python
prefs = client.table("user_preferences") \
    .select("theme") \
    .eq("user_id", user["user_id"]) \
    .execute()

user_theme = prefs.data[0]["theme"] if prefs.data else "light"
```

Passar `user_theme` para o template:
```python
{"request": request, "user": user, "css_version": _CSS_V, "user_theme": user_theme}
```

---

## Frontend

### `base.html`

Aplicar o tema no `<html>` via Jinja2, eliminando o flash de tema:

```html
<html lang="pt-BR" {% if user_theme == 'dark' %}data-theme="dark"{% endif %}>
```

Remover o bloco JavaScript que lê o `localStorage` para aplicar o tema inicial (já não é necessário para o carregamento inicial). Manter o `localStorage` apenas como fallback para a página de login.

### `sidebar.html` — toggle de tema

Adicionar `fetch` ao trocar o tema para persistir no banco:

```javascript
fetch('/user/theme', {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({ theme: dark ? 'light' : 'dark' })
});
```

Manter o `localStorage.setItem` para que a troca seja imediata sem recarregar.

---

## Fluxo Completo

```
1. Usuário acessa /app
   → app_router busca tema no Supabase
   → template renderiza com data-theme correto
   → sem flash de tema

2. Usuário clica no toggle
   → Alpine.js troca data-theme imediatamente
   → localStorage atualizado (resposta imediata)
   → fetch POST /user/theme salva no banco (em background)

3. Usuário abre em outro dispositivo
   → app_router busca tema no Supabase
   → tema correto aplicado desde o primeiro render
```

---

## Arquivos Modificados

| Arquivo | Alteração |
|---------|-----------|
| Supabase | Nova tabela `user_preferences` |
| `app/routers/app_router.py` | Busca tema ao carregar `/app` |
| `app/routers/` (novo arquivo `user.py`) | Endpoint `POST /user/theme` |
| `main.py` | Registrar novo router |
| `app/templates/base.html` | Aplicar tema via Jinja2 no `<html>` |
| `app/templates/partials/sidebar.html` | Adicionar fetch ao toggle de tema |

---

## O que NÃO muda

- O localStorage continua sendo usado para resposta imediata no toggle
- A página de login continua usando localStorage para aplicar tema (usuário não autenticado)
- Nenhuma outra preferência é armazenada nesta entrega
