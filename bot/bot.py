import logging
import os
import time
import asyncio
from typing import Optional

from dotenv import load_dotenv
load_dotenv(override=True)

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
        result = await asyncio.to_thread(groq_client.interpret_text, text)
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

    await _execute_action(action, data, update.message.reply_text, chat_id=chat_id)


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
        text = await asyncio.to_thread(groq_client.transcribe_audio, audio_bytes)
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
