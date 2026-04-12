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


def _escape_html(text: str) -> str:
    """Escapa caracteres especiais para parse_mode=HTML do Telegram."""
    if not text:
        return ""
    return (
        str(text)
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
    )


def _fmt_deadline(deadline: Optional[str]) -> str:
    """Formata o deadline em texto amigável com dias restantes."""
    if not deadline:
        return ""
    from datetime import date, datetime
    import pytz
    try:
        dl = date.fromisoformat(deadline)
        today = datetime.now(pytz.timezone("America/Manaus")).date()
        diff = (dl - today).days
        if diff < 0:
            return f"⚠️ vencida há {abs(diff)}d"
        elif diff == 0:
            return "🔥 vence hoje"
        elif diff == 1:
            return "⏰ vence amanhã"
        else:
            return f"🗓 {diff}d"
    except Exception:
        return str(deadline)


def _clean_name(name: str, limit: int = 70) -> str:
    """Remove quebras de linha e limita o tamanho do nome."""
    if not name:
        return ""
    cleaned = " ".join(str(name).split())
    if len(cleaned) > limit:
        cleaned = cleaned[: limit - 1].rstrip() + "…"
    return cleaned


def format_daily_summary(tasks: list, notes: list, ideas: list) -> str:
    """Monta o resumo diário para envio pelo Telegram (parse_mode=HTML)."""
    from datetime import datetime
    import pytz
    today = datetime.now(pytz.timezone("America/Manaus")).strftime("%d/%m/%Y")

    SEP = "━━━━━━━━━━━━━━━"
    lines = [
        f"🗓 <b>Resumo do dia</b>",
        f"<i>{today}</i>",
        SEP,
    ]

    priority_order = ["critica", "urgente", "normal"]
    priority_titles = {
        "critica": "🔴 <b>Críticas</b>",
        "urgente": "🟠 <b>Urgentes</b>",
        "normal": "⚪ <b>Normais</b>",
    }

    tasks_by_priority = {p: [] for p in priority_order}
    for t in tasks:
        p = t.get("priority", "normal")
        if p in tasks_by_priority:
            tasks_by_priority[p].append(t)

    has_tasks = any(tasks_by_priority[p] for p in priority_order)
    if has_tasks:
        lines.append(f"📋 <b>Tarefas ativas ({len(tasks)})</b>")
        for p in priority_order:
            group = tasks_by_priority[p]
            if not group:
                continue
            lines.append("")
            lines.append(priority_titles[p])
            for t in group:
                name = _escape_html(_clean_name(t.get("name", "")))
                project = t.get("project")
                deadline_str = _fmt_deadline(t.get("deadline"))

                meta_parts = []
                if project:
                    meta_parts.append(f"📁 {_escape_html(project)}")
                if deadline_str:
                    meta_parts.append(deadline_str)

                lines.append(f"▪️ {name}")
                if meta_parts:
                    lines.append(f"   <i>{' · '.join(meta_parts)}</i>")
    else:
        lines.append("✨ <i>Nenhuma tarefa ativa no momento.</i>")

    if notes:
        lines.append("")
        lines.append(SEP)
        lines.append(f"📝 <b>Notas recentes ({min(len(notes), 5)})</b>")
        for n in notes[:5]:
            content = n.get("content", "")
            preview = _clean_name(content, limit=80)
            lines.append(f"▪️ {_escape_html(preview)}")

    if ideas:
        lines.append("")
        lines.append(SEP)
        lines.append(f"💡 <b>Ideias ({min(len(ideas), 5)})</b>")
        for i in ideas[:5]:
            title = _escape_html(_clean_name(i.get("title", "")))
            project = i.get("project")
            if project:
                lines.append(f"▪️ {title} <i>· 📁 {_escape_html(project)}</i>")
            else:
                lines.append(f"▪️ {title}")

    lines.append("")
    lines.append(SEP)
    lines.append(f"📊 Total: <b>{len(tasks)}</b> tarefa(s) ativa(s)")

    return "\n".join(lines)
