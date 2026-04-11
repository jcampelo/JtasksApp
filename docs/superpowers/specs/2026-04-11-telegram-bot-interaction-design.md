# Spec: Bot Telegram — Modelo de Interação e Capacidades

**Data:** 2026-04-11  
**Status:** Aprovado — aguardando plano de implementação  
**Autor:** Jefferson Campelo + Claude  
**Substitui:** `2026-04-10-telegram-voice-bot-design.md` (mantido como referência de stack e infra)

---

## 1. Visão Geral

Bot do Telegram integrado ao JtasksApp que funciona como interface completa à aplicação — equivalente a tudo que o usuário faria pelo app diretamente. Aceita voz e texto de forma intercambiável.

**Princípio central:** rápido para capture, preciso para gestão.

---

## 2. Stack e Infra

Mantida conforme spec anterior:

| Componente | Tecnologia |
|---|---|
| Bot | `python-telegram-bot` v20+ |
| STT | Groq Whisper (`whisper-large-v3`) |
| NLP | Groq LLaMA (`llama-3.3-70b-versatile`) |
| Backend | JtasksApp FastAPI (interno via HTTP + API Key) |
| Infra | VPS existente, serviço systemd separado (`jtasks-bot`) |

---

## 3. Ações Suportadas

### 3.1 Capture

| Ação | Exemplos de frase |
|---|---|
| Criar tarefa | "Cria tarefa urgente: reunião com cliente amanhã" |
| Criar nota | "Anota: lembrar de enviar o contrato" / "salva isso aqui: ..." |
| Criar ideia | "Ideia: criar dashboard de métricas no projeto X" |

**Regras:**
- Quando o usuário não especifica nota ou ideia, o padrão é **nota**
- Se o usuário diz explicitamente "ideia", cria ideia; se diz "nota", cria nota
- Campos inferidos do contexto: nome, projeto, prioridade, prazo (tarefas); conteúdo (notas); título + descrição + projeto (ideias)

### 3.2 Gestão de Tarefas

| Ação | Exemplos de frase |
|---|---|
| Listar tarefas ativas | "Quais minhas tarefas?" / "O que tenho pra fazer?" |
| Listar tarefas do dia | "O que tenho pra hoje?" |
| Listar tarefas atrasadas | "Quais estão atrasadas?" |
| Ver detalhes de uma tarefa | "Me mostra a tarefa reunião com cliente" |
| Marcar como concluída | "Concluí a reunião com cliente" |
| Marcar como descartada | "Descarta a tarefa reunião com cliente" |
| Mudar prioridade | "Muda a reunião com cliente pra crítica" |
| Atualizar prazo | "Muda o prazo da reunião pra sexta" |
| Adicionar update | "Adiciona update na reunião: cliente confirmou presença" |

### 3.3 Gestão de Notas e Ideias

| Ação | Exemplos de frase |
|---|---|
| Listar notas | "Minhas notas" |
| Listar ideias | "Minhas ideias" |
| Deletar nota | "Deleta aquela nota sobre o contrato" |
| Deletar ideia | "Deleta a ideia do dashboard" |

**Fora de escopo (v1):** gerenciamento de checklist de tarefas (fica disponível apenas no app).

---

## 4. Modelo de Interação

### 4.1 Abordagem geral: Linguagem Natural com Menu de Contexto

- Entrada: frases livres (voz ou texto)
- O LLM interpreta intenção e extrai campos
- Quando precisar selecionar entre múltiplas opções, usa **botões inline do Telegram** (não pede texto)

### 4.2 Fluxo Capture — inferência com confirmação seletiva

**Alta confiança → executa direto:**
```
Usuário: "cria tarefa urgente reunião com cliente amanhã"
Bot:     ✅ Tarefa criada: "Reunião com cliente"
         Prioridade: urgente | Prazo: 12/04/2026
```

**Baixa confiança → pede o campo em falta:**
```
Usuário: "cria uma tarefa sobre aquela reunião"
Bot:     Entendi que você quer criar uma tarefa.
         Qual o nome da tarefa?
```

### 4.3 Fluxo Gestão — desambiguação por botões inline

**Uma tarefa encontrada → executa direto:**
```
Usuário: "conclui a tarefa reunião com cliente"
Bot:     ✅ Tarefa "Reunião com cliente" marcada como concluída.
```

**Múltiplas encontradas → botões inline:**
```
Usuário: "conclui a tarefa reunião"
Bot:     Qual tarefa você quer concluir?
         [Reunião com cliente]  [Reunião interna]  [Cancelar]

Usuário: *toca em "Reunião com cliente"*
Bot:     ✅ Tarefa "Reunião com cliente" marcada como concluída.
```

### 4.4 Fluxo Listagem

```
Usuário: "quais minhas tarefas de hoje?"
Bot:     📋 Tarefas para hoje (3):

         🔴 Reunião com cliente — urgente
         🟠 Enviar proposta — urgente
         ⚪ Revisar contrato — normal
```

**Ícones de prioridade:**
- 🔴 crítica
- 🟠 urgente
- ⚪ normal

### 4.5 Confirmação pendente

- Ações que aguardam seleção de botão ou resposta de confirmação expiram em **60 segundos**
- Qualquer nova mensagem antes de responder cancela a ação pendente e processa a nova mensagem
- Estado de confirmação pendente armazenado em memória (dicionário por `chat_id`)

---

## 5. Descoberta e Ajuda

### 5.1 Menu nativo do Telegram (botão `/`)

Comandos registrados no BotFather para aparecer no menu de atalhos:

| Comando | Ação |
|---|---|
| `/tarefas` | Lista tarefas ativas |
| `/hoje` | Tarefas com prazo para hoje |
| `/atrasadas` | Tarefas com prazo vencido |
| `/notas` | Lista notas |
| `/ideias` | Lista ideias |
| `/help` | Guia completo de comandos e exemplos |

### 5.2 Resposta do /help

Texto formatado com seções:
- **Capture** — exemplos de criação de tarefa, nota e ideia
- **Gestão de tarefas** — exemplos de listar, concluir, atualizar
- **Notas e ideias** — exemplos de listar e deletar
- **Dica:** "Você pode falar ou digitar naturalmente — não precisa usar comandos exatos."

---

## 6. Tratamento de Erros

### 6.1 Erros de interpretação

| Situação | Resposta |
|---|---|
| Áudio ininteligível (Whisper retorna vazio) | "Não consegui entender o áudio. Pode repetir com mais clareza?" |
| Intenção desconhecida | "Não entendi. Digite /help para ver o que posso fazer." |
| Tarefa não encontrada | "Não encontrei nenhuma tarefa com esse nome." |
| Múltiplos resultados | Exibe botões inline para seleção |

### 6.2 Erros de sistema

| Situação | Resposta |
|---|---|
| Groq indisponível / timeout | "Serviço de IA indisponível no momento. Tente em instantes." |
| JtasksApp offline | "Não consegui conectar ao app. Tente novamente." |
| Áudio > 25MB | "Áudio muito longo. Envie mensagens mais curtas." |

---

## 7. Autenticação

Mantida conforme spec anterior:
- Bot → JtasksApp via header `X-Bot-Key`
- `BOT_OWNER_USER_ID` no `.env` identifica o usuário dono
- Escopo atual: uso pessoal (1 usuário)
- Arquitetura preparada para multi-usuário via mapeamento `telegram_user_id → supabase_user_id`

---

## 8. Estrutura de Arquivos

```
JtasksApp/
├── bot/
│   ├── bot.py           # Entry point: inicializa o bot, registra handlers e comandos
│   ├── groq_client.py   # STT (Whisper) + NLP (LLaMA)
│   ├── actions.py       # Chamadas HTTP aos endpoints internos do JtasksApp
│   ├── prompts.py       # Prompt do sistema para o LLaMA
│   └── formatters.py    # Formata respostas do bot (listas, detalhes, emojis)
├── app/
│   └── routers/
│       └── bot_api.py   # Endpoints JSON exclusivos para o bot (/bot/*)
└── .env
```

`formatters.py` é novo em relação à spec anterior — centraliza toda a formatação de mensagens do bot (listas de tarefas, detalhes, confirmações).

---

## 9. Endpoints do Bot (`bot_api.py`)

Todos em `/bot/`, retornam JSON, autenticados via `X-Bot-Key`.

| Método | Rota | Ação |
|---|---|---|
| POST | `/bot/tasks` | Criar tarefa |
| GET | `/bot/tasks` | Listar tarefas (filtro: `status`, `today`, `overdue`) |
| GET | `/bot/tasks/{id}` | Detalhes de uma tarefa |
| PATCH | `/bot/tasks/{id}` | Atualizar prioridade ou prazo |
| POST | `/bot/tasks/{id}/complete` | Marcar como concluída |
| POST | `/bot/tasks/{id}/discard` | Marcar como descartada |
| POST | `/bot/tasks/{id}/updates` | Adicionar update |
| GET | `/bot/tasks/search` | Buscar tarefas por nome (deve ser declarado antes de `/{id}`) |
| POST | `/bot/notes` | Criar nota |
| GET | `/bot/notes` | Listar notas |
| GET | `/bot/notes/search` | Buscar notas por conteúdo (deve ser declarado antes de `/{id}`) |
| DELETE | `/bot/notes/{id}` | Deletar nota |
| POST | `/bot/ideas` | Criar ideia |
| GET | `/bot/ideas` | Listar ideias |
| GET | `/bot/ideas/search` | Buscar ideias por título (deve ser declarado antes de `/{id}`) |
| DELETE | `/bot/ideas/{id}` | Deletar ideia |

---

## 10. Schema de Resposta do LLaMA

```json
{
  "action": "create_task | create_note | create_idea | list_tasks | list_notes | list_ideas | get_task | complete_task | discard_task | update_priority | update_deadline | add_update | delete_note | delete_idea | unknown",
  "confidence": "high | low",
  "data": {
    "name": "string ou null",
    "priority": "critica | urgente | normal",
    "deadline": "YYYY-MM-DD ou null",
    "project": "string ou null",
    "content": "string ou null",
    "title": "string ou null",
    "description": "string ou null",
    "update_text": "string ou null",
    "filter": "today | overdue | active | null",
    "search_term": "string ou null"
  },
  "clarification_needed": "mensagem explicando a dúvida (apenas se confidence=low)"
}
```

---

## 11. Variáveis de Ambiente

```env
TELEGRAM_BOT_TOKEN=<token do @BotFather>
GROQ_API_KEY=<key do console.groq.com>
BOT_API_KEY=<gerado com secrets.token_hex(32)>
BOT_OWNER_USER_ID=<UUID do Supabase Auth>
JTASKS_INTERNAL_URL=http://localhost:8000
```

---

## 12. Dependências Python

```
python-telegram-bot==20.7
groq>=0.9.0
httpx>=0.27.0
```

---

## 13. Pré-requisitos Manuais

1. Criar bot no `@BotFather` e copiar token
2. Registrar comandos do menu no BotFather (`/setcommands`)
3. Criar conta no Groq e gerar API Key
4. Copiar `BOT_OWNER_USER_ID` do painel do Supabase
5. Gerar `BOT_API_KEY`: `python -c "import secrets; print(secrets.token_hex(32))"`

---

## 14. Ordem de Implementação

1. Adicionar variáveis ao `config.py`
2. Criar `app/routers/bot_api.py` com todos os endpoints
3. Registrar router em `main.py`
4. Criar `bot/prompts.py`
5. Criar `bot/groq_client.py` (STT + NLP)
6. Criar `bot/formatters.py` (formatação de respostas)
7. Criar `bot/actions.py` (chamadas HTTP)
8. Criar `bot/bot.py` (handlers, comandos, botões inline, confirmação pendente)
9. Atualizar `requirements.txt`
10. Testar localmente em modo polling
11. Criar serviço systemd no VPS e ativar

---

## 15. Critérios de Sucesso

- [ ] Voz e texto funcionam de forma intercambiável
- [ ] "Cria tarefa urgente: reunião amanhã" → tarefa aparece no JtasksApp sem nenhuma pergunta adicional
- [ ] "Conclui a reunião" com duas tarefas parecidas → exibe botões inline para escolha
- [ ] `/tarefas` e `/hoje` funcionam como atalhos rápidos
- [ ] `/help` retorna guia organizado por categoria
- [ ] Bot continua rodando após reinício do VPS (systemd)
- [ ] Falha no Groq não derruba o JtasksApp
