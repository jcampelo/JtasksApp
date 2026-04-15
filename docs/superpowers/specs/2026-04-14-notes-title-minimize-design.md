# Notes: Título + Minimizar — Design Spec

**Data:** 2026-04-14  
**Status:** Aprovado pelo usuário

---

## Contexto

As notas (post-its) atualmente possuem apenas `content` e `color`. Com o acúmulo de notas, fica difícil identificar o tema de cada uma. O usuário quer poder dar um título para cada nota e minimizar as que não precisam ficar visíveis.

**Decisões tomadas no brainstorming:**
- Opção A: título por nota + botão minimizar (sem tags/agrupamento)
- Título obrigatório
- Notas existentes: migration preenche título com os primeiros 40 chars do `content`
- Estado minimizado: localStorage (per-device, sem sync entre browsers)

---

## Schema — Supabase

Adicionar coluna `title` à tabela `notes`.

**Migration (rodar no SQL Editor do Supabase):**
```sql
ALTER TABLE notes ADD COLUMN title TEXT;
UPDATE notes SET title = LEFT(content, 40) WHERE title IS NULL;
ALTER TABLE notes ALTER COLUMN title SET NOT NULL;
```

Não há migration automática — rodar manualmente antes do deploy.

---

## Backend (`app/routers/notes.py`)

### `POST /notes`
- Cria nota com `title = "Nova nota"` e `content = ""` (placeholder — usuário edita inline)
- Insere `title` no payload do Supabase

### `PATCH /notes/{note_id}`
- Já aceita `content` e `color` via `Form(None)` (opcionais)
- Adicionar `title: Optional[str] = Form(None)` com a mesma lógica
- Se `title` vier preenchido no `update_data`, incluir; se vier string vazia, **ignorar** (preserva último valor válido — tolerância para auto-save durante digitação)

### `POST /notes/{note_id}/convert`
- Atualmente seleciona apenas `content` e usa como nome da tarefa
- Após a mudança, novas notas terão `content = ""` — converter geraria tarefas com nome vazio
- **Fix:** selecionar `title` e `content`; usar `title` como `name` da tarefa (fallback: `content[:40]` se title vazio por algum motivo)

### Sem novos endpoints
A lógica de minimizar fica 100% no frontend (localStorage). Nenhuma rota nova necessária.

---

## Frontend (`app/templates/partials/notes/notes_list.html`)

### Estrutura do post-it (expandido)
```
┌─────────────────────────────┐
│ ● ● ● ●        [📋]  ▲  ✕  │  ← header: cores + converter + minimizar + excluir
│ [input: Título da nota    ] │  ← <input> inline, auto-save HTMX
│                             │
│ [textarea: Conteúdo...    ] │  ← existente, oculto quando minimizado
└─────────────────────────────┘
```

### Estrutura do post-it (minimizado)
```
┌─────────────────────────────┐
│ Título da nota         ▼ ✕  │  ← só o header visível (cores + converter ocultos)
└─────────────────────────────┘
```

### Alpine.js — estado minimizado
Cada post-it usa `x-data` com:
- `minimized`: bool inicializado lendo `localStorage` (`notes_minimized` → array de IDs)
- Método `toggle()`: inverte estado, grava array atualizado no localStorage
- Chave localStorage: `notes_minimized` (array de UUIDs)

```js
// Exemplo de x-data no post-it
{
  minimized: false,
  init() {
    const ids = JSON.parse(localStorage.getItem('notes_minimized') || '[]');
    this.minimized = ids.includes('{{ note.id }}');
  },
  toggle() {
    let ids = JSON.parse(localStorage.getItem('notes_minimized') || '[]');
    if (this.minimized) {
      ids = ids.filter(id => id !== '{{ note.id }}');
    } else {
      ids.push('{{ note.id }}');
    }
    localStorage.setItem('notes_minimized', JSON.stringify(ids));
    this.minimized = !this.minimized;
  }
}
```

### Auto-save do título
- `<input>` com `hx-patch="/notes/{{ note.id }}"`, `hx-trigger="keyup changed delay:500ms"`, `name="title"`
- `hx-target` e `hx-swap="none"` (sem re-render da lista inteira a cada keystroke)
- Sem toast no auto-save de título (igual ao comportamento atual do textarea)

### CSS
- Input de título: `background: transparent; border: none; font-weight: 600; width: 100%`
- Estado minimizado: `display: none` no `.post-it-body` e no color-picker via `x-show="!minimized"`
- Botão minimizar: ▲ quando expandido, ▼ quando minimizado
- Post-it minimizado: `min-height` reduzido (não mais 200px fixo)

---

## Comportamento do `POST /notes` (criar nova nota)

Atualmente cria com `content = "Nova nota"`. Após a mudança:
- `title = "Nova nota"`
- `content = ""`
- O usuário clica no título inline e edita; o corpo fica vazio até digitar

---

## Validação

| Cenário | Comportamento |
|---|---|
| Título vazio no auto-save | Backend ignora update (preserva valor anterior) |
| Nota criada sem título | Impossível — `POST /notes` sempre insere `title = "Nova nota"` |
| Notas legadas sem título | Migration preenche com `LEFT(content, 40)` |

---

## Arquivos afetados

| Arquivo | Mudança |
|---|---|
| `app/routers/notes.py` | Adicionar `title` em `POST` e `PATCH` |
| `app/templates/partials/notes/notes_list.html` | Input de título, botão minimizar, Alpine.js x-data, CSS |
| Supabase (manual) | Migration SQL antes do deploy |

---

## O que NÃO muda

- Lógica de cores (color picker)
- Botão "Converter em atividade"
- Auto-save do textarea de conteúdo
- Delete de nota
- Dark mode (classes já existentes cobrem os novos elementos)
