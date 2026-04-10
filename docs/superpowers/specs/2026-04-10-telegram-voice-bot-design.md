# Spec: Bot Telegram com Voz para JtasksApp

**Data:** 2026-04-10  
**Status:** Aprovado — aguardando implementação  
**Autor:** Jefferson Campelo + Claude

---

## 1. Visão Geral

Integrar um bot do Telegram ao JtasksApp que permita ao usuário enviar **mensagens de voz** e executar ações na aplicação de forma natural, como se estivesse falando com um assistente.

**Exemplo de uso:**
> Usuário envia áudio: *"Cria uma tarefa urgente: ligar para o cliente amanhã"*  
> Bot responde: *"✅ Tarefa criada: 'Ligar para o cliente' — prioridade urgente"*

---

## 2. Requisitos

### Funcionais
- Receber áudio via Telegram e transcrever para texto (STT)
- Interpretar a intenção do texto com LLM
- Executar as seguintes ações:
  - Criar tarefa (com nome, projeto, prioridade, prazo)
  - Criar nota
  - Criar ideia
  - Listar tarefas do dia
  - Marcar tarefa como concluída
- Quando a confiança na interpretação for baixa, confirmar antes de executar
- Responder sempre em texto (não em voz)

### Não-funcionais
- Custo zero (usar free tiers)
- Rodar no mesmo VPS do JtasksApp como serviço systemd separado
- Escopo atual: uso pessoal (1 usuário), mas arquitetura preparada para multi-usuário futuro
- Respostas em português brasileiro

---

## 3. Stack Tecnológica

| Componente | Tecnologia | Custo |
|---|---|---|
| Bot Telegram | `python-telegram-bot` v20+ | Gratuito |
| STT (voz → texto) | Groq Whisper (`whisper-large-v3`) | Gratuito (free tier) |
| NLP (texto → intenção) | Groq LLaMA (`llama-3.3-70b-versatile`) | Gratuito (free tier) |
| Backend | JtasksApp FastAPI (já existente) | — |
| Infra | VPS existente via systemd | — |

**Limites do Groq free tier (referência em 2026-04-10):**
- Whisper: ~7.200 segundos de áudio/dia
- LLaMA 3.3 70b: ~14.400 tokens/dia  
*(Monitorar em console.groq.com — podem mudar)*

---

## 4. Arquitetura

### Estrutura de arquivos

```
JtasksApp/
├── bot/
│   ├── bot.py           # Entry point: inicializa o bot, registra handlers
│   ├── groq_client.py   # Funções de STT (Whisper) e NLP (LLaMA)
│   ├── actions.py       # Chama endpoints internos do JtasksApp via HTTP
│   └── prompts.py       # Prompt do sistema para o LLaMA
├── app/
│   └── routers/
│       └── bot_api.py   # Novos endpoints JSON exclusivos para o bot
└── .env                 # Variáveis de ambiente (já existente, adicionar novas)
```

### Fluxo de dados

```
1. Usuário envia áudio OGG no Telegram
2. bot.py recebe o arquivo e faz download temporário
3. groq_client.py envia o arquivo para Groq Whisper
4. Groq Whisper retorna texto transcrito
5. groq_client.py envia texto + prompt para Groq LLaMA
6. LLaMA retorna JSON com { action, confidence, data }
7a. Se confidence = "high"  → actions.py chama endpoint do JtasksApp
7b. Se confidence = "low"   → bot responde pedindo confirmação ao usuário
8. Se confirmado → actions.py executa a ação
9. Bot envia mensagem de confirmação ao usuário
```

---

## 5. Autenticação Bot ↔ JtasksApp

O bot se comunica com o JtasksApp via HTTP interno (`http://localhost:PORT`).

**Mecanismo:** API Key interna

- O bot envia o header `X-Bot-Key: <BOT_API_KEY>` em todas as requisições
- O router `bot_api.py` valida a key contra a variável de ambiente `BOT_API_KEY`
- O `BOT_OWNER_USER_ID` (no `.env`) identifica o usuário dono do bot
- No futuro, para multi-usuário: mapear `telegram_user_id → supabase_user_id` em tabela

**Dependência de autenticação no bot_api.py:**
```python
def verify_bot_key(x_bot_key: str = Header(...)):
    if x_bot_key != settings.BOT_API_KEY:
        raise HTTPException(status_code=403, detail="Forbidden")
    return True
```

---

## 6. Endpoints do Bot (`bot_api.py`)

Todos os endpoints são exclusivos para o bot, retornam JSON e ficam em `/bot/`.

### POST `/bot/tasks`
Cria uma tarefa.

**Headers:** `X-Bot-Key`

**Body JSON:**
```json
{
  "name": "Nome da tarefa",
  "project": "Nome do projeto ou null",
  "priority": "critica | urgente | normal",
  "deadline": "YYYY-MM-DD ou null"
}
```

**Response 200:**
```json
{ "ok": true, "task_id": "uuid" }
```

---

### POST `/bot/notes`
Cria uma nota.

**Body JSON:**
```json
{ "content": "Conteúdo da nota" }
```

**Response 200:**
```json
{ "ok": true, "note_id": "uuid" }
```

---

### POST `/bot/ideas`
Cria uma ideia.

**Body JSON:**
```json
{
  "title": "Título da ideia",
  "description": "Descrição ou null",
  "project": "Nome do projeto ou null"
}
```

**Response 200:**
```json
{ "ok": true, "idea_id": "uuid" }
```

---

### GET `/bot/tasks/today`
Lista tarefas ativas do dia atual.

**Response 200:**
```json
{
  "tasks": [
    { "id": "uuid", "name": "...", "priority": "urgente", "deadline": "2026-04-10" }
  ]
}
```

---

### POST `/bot/tasks/{task_id}/complete`
Marca uma tarefa como concluída.

**Response 200:**
```json
{ "ok": true }
```

---

## 7. Schema de Resposta do LLaMA

O LLaMA sempre retorna um JSON com este schema. O prompt deve instruí-lo a nunca retornar texto livre:

```json
{
  "action": "create_task | create_note | create_idea | list_tasks | complete_task | unknown",
  "confidence": "high | low",
  "data": {
    "name": "string ou null",
    "priority": "critica | urgente | normal",
    "deadline": "YYYY-MM-DD ou null",
    "project": "string ou null",
    "content": "string ou null",
    "title": "string ou null",
    "description": "string ou null"
  },
  "clarification_needed": "mensagem explicando a dúvida, preenchido apenas se confidence=low"
}
```

**Regras do prompt:**
- Se o usuário mencionar "urgente", "crítico", "importante" → mapear para priority
- Se mencionar data relativa ("amanhã", "sexta") → converter para YYYY-MM-DD baseado na data atual
- Se a intenção for ambígua → `confidence: low` com `clarification_needed` explicando

---

## 8. Lógica de Confirmação

Quando `confidence = "low"`:

1. Bot responde: *"Entendi: [ação]. [clarification_needed]. Confirma? (sim/não)"*
2. Bot armazena a ação pendente em memória (dicionário por `chat_id`)
3. Próxima mensagem do usuário:
   - Se contiver "sim", "confirmo", "pode", "ok" → executa
   - Qualquer outra coisa → cancela e responde "Cancelado."
4. A ação pendente expira após 60 segundos sem resposta

---

## 9. Tratamento de Erros

| Situação | Resposta do bot |
|---|---|
| Áudio ininteligível (Whisper retorna string vazia) | "Não consegui entender o áudio. Pode repetir com mais clareza?" |
| LLaMA retorna `action: unknown` | "Não entendi o que você quis dizer. Tente reformular." |
| Groq API offline / timeout | "O serviço de IA está indisponível no momento. Tente em instantes." |
| Endpoint JtasksApp retorna erro | "Não consegui salvar. Tente novamente." |
| Arquivo de áudio muito grande (>25MB) | "Áudio muito longo. Envie mensagens mais curtas." |

---

## 10. Variáveis de Ambiente

Adicionar ao `.env` existente do JtasksApp:

```env
# Telegram Bot
TELEGRAM_BOT_TOKEN=<token do @BotFather>

# Groq
GROQ_API_KEY=<key do console.groq.com>

# Autenticação interna bot ↔ JtasksApp
BOT_API_KEY=<string aleatória segura, ex: gerada com secrets.token_hex(32)>
BOT_OWNER_USER_ID=<seu user_id do Supabase Auth (UUID)>

# URL interna do JtasksApp (padrão: localhost)
JTASKS_INTERNAL_URL=http://localhost:8000
```

---

## 11. Serviço Systemd

Criar o arquivo `/etc/systemd/system/jtasks-bot.service` no VPS:

```ini
[Unit]
Description=JtasksApp Telegram Bot
After=network.target jtasks.service

[Service]
WorkingDirectory=/caminho/para/JtasksApp
ExecStart=/caminho/para/venv/bin/python bot/bot.py
Restart=always
RestartSec=5
EnvironmentFile=/caminho/para/JtasksApp/.env
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
```

**Comandos para ativar:**
```bash
sudo systemctl daemon-reload
sudo systemctl enable jtasks-bot
sudo systemctl start jtasks-bot
sudo systemctl status jtasks-bot
```

---

## 12. Dependências Python

Adicionar ao `requirements.txt`:

```
python-telegram-bot==20.7
groq>=0.9.0
httpx>=0.27.0
```

*(O `groq` SDK usa `httpx` internamente, mas é bom declarar explicitamente)*

---

## 13. Pré-requisitos Manuais (feitos pelo usuário)

Antes de iniciar a implementação, o usuário precisa:

1. **Criar o bot no Telegram:**
   - Abrir `@BotFather` no Telegram
   - Enviar `/newbot`
   - Escolher nome e username
   - Copiar o token gerado → colocar em `TELEGRAM_BOT_TOKEN`

2. **Criar conta e obter API Key do Groq:**
   - Acessar `console.groq.com`
   - Criar conta (gratuita, sem cartão)
   - Gerar API Key → colocar em `GROQ_API_KEY`

3. **Descobrir seu `user_id` do Supabase:**
   - Acessar o painel do Supabase → Authentication → Users
   - Copiar o UUID do seu usuário → colocar em `BOT_OWNER_USER_ID`

4. **Gerar o `BOT_API_KEY`:**
   - Rodar no terminal: `python -c "import secrets; print(secrets.token_hex(32))"`
   - Copiar o resultado → colocar em `BOT_API_KEY`

---

## 14. Ordem de Implementação

Quando o usuário solicitar a implementação, seguir esta ordem:

1. Adicionar variáveis ao `config.py` (Pydantic Settings)
2. Criar `app/routers/bot_api.py` com todos os endpoints
3. Registrar o router em `main.py`
4. Criar `bot/prompts.py` com o prompt do sistema
5. Criar `bot/groq_client.py` (STT + NLP)
6. Criar `bot/actions.py` (chamadas HTTP aos endpoints)
7. Criar `bot/bot.py` (handlers Telegram, lógica de confirmação)
8. Atualizar `requirements.txt`
9. Testar localmente com bot em modo polling
10. Criar serviço systemd no VPS e ativar

---

## 15. Critérios de Sucesso

- [ ] Usuário envia áudio "cria tarefa urgente: reunião amanhã" → tarefa aparece no JtasksApp
- [ ] Usuário envia áudio ambíguo → bot pede confirmação antes de executar
- [ ] Usuário envia áudio "quais minhas tarefas hoje" → bot lista as tarefas
- [ ] Bot continua rodando após reinício do VPS (systemd)
- [ ] Falha no Groq não derruba o JtasksApp (processos isolados)
