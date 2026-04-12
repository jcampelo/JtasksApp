# Resumo Diário no Telegram

## O que é

Todo dia, no horário configurado na tela de Notificações, o bot envia automaticamente uma mensagem no seu Telegram com:

- Tarefas ativas agrupadas por prioridade (crítica, urgente, normal) com prazos
- Notas recentes (últimas 5)
- Ideias recentes (últimas 5)
- Contagem total de tarefas ativas

Cada tarefa exibe um botão inline ✅ para marcá-la como concluída diretamente da mensagem, sem precisar abrir o app.

## Variáveis de ambiente necessárias

Adicione ao `.env` na VPS:

```env
TELEGRAM_CHAT_ID=<seu_chat_id>
```

As demais variáveis (`TELEGRAM_BOT_TOKEN`, `BOT_API_KEY`) já devem estar configuradas para o bot funcionar.

## Como obter o TELEGRAM_CHAT_ID

1. Abra o Telegram e inicie uma conversa com seu bot (envie `/start`)
2. Acesse no browser:
   ```
   https://api.telegram.org/bot<SEU_TOKEN>/getUpdates
   ```
3. Procure o campo `"chat": {"id": XXXXXXXX}` na resposta JSON
4. Esse número é o seu `TELEGRAM_CHAT_ID`

## Como ativar

1. Acesse o app → menu lateral → **Notificações**
2. Marque a opção **"Habilitar resumo diário no Telegram"**
3. Clique em **Salvar configuração**

O horário de envio é o mesmo configurado para o email. Para alterar, basta mudar o campo **Horário de envio** e salvar.

## Arquitetura

```
APScheduler (telegram_daily_{user_id})
    ↓ no horário configurado
_run_telegram_job()
    ↓
GET /bot/tasks?filter=active
GET /bot/notes
GET /bot/ideas
    ↓
format_daily_summary(tasks, notes, ideas)
    ↓
POST https://api.telegram.org/bot{TOKEN}/sendMessage
    com reply_markup (botões inline por tarefa)
    ↓
Telegram → mensagem no chat do usuário
```

## Arquivos modificados

| Arquivo | Alteração |
|---|---|
| `app/config.py` | Campo `telegram_chat_id` adicionado ao Settings |
| `app/routers/notify.py` | Parâmetro `telegram_enabled` no form de config |
| `app/scheduler.py` | Função `_run_telegram_job` + job `telegram_daily_*` no `reschedule()` |
| `app/templates/partials/notify/notify_tab.html` | Checkbox para habilitar o resumo no Telegram |
| `bot/formatters.py` | Função `format_daily_summary` |

## Comportamento do scheduler

- O job `telegram_daily_{user_id}` é criado/removido automaticamente ao salvar a configuração
- Se `TELEGRAM_CHAT_ID` ou `TELEGRAM_BOT_TOKEN` não estiverem definidos, o job é pulado com log de aviso
- Erros de rede ou API do Telegram são capturados e logados sem derrubar o scheduler

## Exemplo de mensagem enviada

```
📅 Resumo do dia — 12/04/2025

📋 Tarefas ativas:

🔴 Críticas:
  • Entregar relatório Q1 [Financeiro] 🔥 vence hoje
  • Reunião com cliente ⏰ vence amanhã

🟠 Urgentes:
  • Revisar proposta comercial (3d)

⚪ Normais:
  • Organizar arquivos do servidor

📝 Notas recentes (2):
  • Lembrar de ligar para o fornecedor antes das 18h
  • Ideia de melhoria no fluxo de onboarding

💡 Ideias (1):
  • App de controle de ponto integrado

—
📊 4 ativa(s)
```
