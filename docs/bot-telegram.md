# Bot Telegram — JtasksApp

Bot de captura rápida e gerenciamento de tarefas via Telegram, com suporte a voz (Groq Whisper) e linguagem natural (LLaMA 3.3-70b).

---

## Arquitetura

```
Telegram → bot/bot.py → bot/groq_client.py (LLM/STT) → bot/actions.py → FastAPI /bot/* → Supabase
```

- **`bot/bot.py`** — handlers de mensagem, voz, callbacks inline, comandos
- **`bot/groq_client.py`** — transcrição de áudio (Whisper) e interpretação de texto (LLaMA)
- **`bot/prompts.py`** — system prompt com ações disponíveis e regras de interpretação
- **`bot/actions.py`** — cliente HTTP para a API interna do JtasksApp
- **`bot/formatters.py`** — formatação das respostas em Markdown para o Telegram
- **`app/routers/bot_api.py`** — endpoints FastAPI protegidos por `X-Bot-Key`

---

## Variáveis de ambiente necessárias (.env)

```env
TELEGRAM_BOT_TOKEN=<token do BotFather>
GROQ_API_KEY=<chave da conta Groq>
BOT_API_KEY=<string hex gerada com secrets.token_hex(32)>
BOT_OWNER_USER_ID=<UUID do usuário no Supabase>
JTASKS_INTERNAL_URL=http://localhost:8080
```

> **Importante:** `BOT_API_KEY` é uma chave interna gerada por você — não é o token do Telegram.
> Gere com: `python -c "import secrets; print(secrets.token_hex(32))"`

---

## Como obter os valores

| Variável | Como obter |
|----------|-----------|
| `TELEGRAM_BOT_TOKEN` | BotFather no Telegram → `/newbot` |
| `GROQ_API_KEY` | console.groq.com → API Keys |
| `BOT_API_KEY` | `python -c "import secrets; print(secrets.token_hex(32))"` |
| `BOT_OWNER_USER_ID` | Supabase Dashboard → Authentication → Users → copiar UUID |
| `JTASKS_INTERNAL_URL` | `http://localhost:8080` local / `http://localhost:8080` VPS |

---

## Rodar localmente

Requer dois terminais:

**Terminal 1 — FastAPI:**
```bash
python main.py
```

**Terminal 2 — Bot:**
```bash
python -m bot.bot
```

> Usar `python -m bot.bot` (não `python bot/bot.py`) para evitar circular import.

---

## Deploy no VPS (systemd)

### Serviço criado em `/etc/systemd/system/jtasks-bot.service`:

```ini
[Unit]
Description=JtasksApp Telegram Bot
After=network.target jtasks.service

[Service]
WorkingDirectory=/home/jtasks/JtasksApp
ExecStart=/home/jtasks/JtasksApp/venv/bin/python3 -m bot.bot
Restart=always
RestartSec=10
EnvironmentFile=/home/jtasks/JtasksApp/.env

[Install]
WantedBy=multi-user.target
```

### Comandos para gerenciar o serviço:

```bash
# Status
sudo systemctl status jtasks-bot

# Reiniciar
sudo systemctl restart jtasks-bot

# Ver logs em tempo real
sudo journalctl -u jtasks-bot -f

# Parar
sudo systemctl stop jtasks-bot
```

---

## Atualizar o bot no VPS

O deploy é automático via CI/CD (push na branch `master`). O serviço do FastAPI (`jtasks`) é reiniciado automaticamente. O bot (`jtasks-bot`) **não é reiniciado automaticamente** — reinicie manualmente após atualizações:

```bash
sudo systemctl restart jtasks-bot
```

> Considere adicionar o restart do bot ao workflow de deploy `.github/workflows/deploy.yml` se quiser automação completa.

---

## Dependências adicionadas (requirements.txt)

```
python-telegram-bot==20.8
groq>=0.9.0
httpx>=0.26.0,<0.28.0
```

> A restrição do `httpx` é necessária para compatibilidade entre `python-telegram-bot==20.8` (requer `~=0.26.0`) e `supabase==2.9.0` (requer `<0.28`).

---

## Ações suportadas pelo bot

| Ação | Exemplo de mensagem |
|------|-------------------|
| Criar tarefa | "Cria tarefa urgente: reunião com cliente amanhã" |
| Criar nota | "Anota: lembrar de enviar o contrato" |
| Criar ideia | "Ideia: novo dashboard de métricas" |
| Listar tarefas | "Quais minhas tarefas?" / "O que tenho pra hoje?" |
| Tarefas atrasadas | "Quais estão atrasadas?" |
| Ver tarefa | "Me mostra a tarefa reunião com cliente" |
| Concluir tarefa | "Concluí a reunião com cliente" |
| Descartar tarefa | "Descarta a tarefa X" |
| Mudar prioridade | "Muda a prioridade da reunião pra crítica" |
| Mudar prazo | "Muda o prazo da reunião pra sexta" |
| Adicionar update | "Adiciona update na reunião: cliente confirmou" |
| Listar notas | "Minhas notas" |
| Listar ideias | "Minhas ideias" |
| Deletar nota | "Deleta aquela nota sobre o contrato" |
| Deletar ideia | "Deleta a ideia do dashboard" |

Também suporta **mensagens de voz** — o áudio é transcrito automaticamente antes de ser processado.

---

## Comandos disponíveis no Telegram

| Comando | Descrição |
|---------|-----------|
| `/tarefas` | Lista tarefas ativas |
| `/hoje` | Lista tarefas de hoje |
| `/atrasadas` | Lista tarefas atrasadas |
| `/notas` | Lista notas |
| `/ideias` | Lista ideias |
| `/help` | Exibe ajuda |

---

## Problemas conhecidos e soluções

### `ModuleNotFoundError: No module named 'telegram'`
```bash
pip install "python-telegram-bot==20.8"
```

### `circular import` ao rodar `python bot/bot.py`
Use sempre `python -m bot.bot`.

### `KeyError: 'TELEGRAM_BOT_TOKEN'`
O `.env` não está sendo carregado. O bot usa `load_dotenv(override=True)` — verifique se o `.env` está na raiz do projeto.

### `InvalidToken` — token rejeitado
Verifique se o token no `.env` está completo (sem cortes). Use `override=True` no `load_dotenv` para garantir que variáveis de sessão não sobrescrevam o `.env`.

### `[WinError 10061]` — conexão recusada
O servidor FastAPI não está rodando. Suba com `python main.py` antes de iniciar o bot.

### Conflito de dependências `httpx` no VPS
`python-telegram-bot==20.8` requer `httpx~=0.26.0`. Use `httpx>=0.26.0,<0.28.0` no `requirements.txt`.

### `,SUPABASE_URL` no `.env` do VPS
Vírgula acidental no início da linha causa `ValidationError` no pydantic. Edite o `.env` e remova a vírgula.
