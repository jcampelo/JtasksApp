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


def _fmt_deadline(deadline: Optional[str]) -> str:
    """Formata o deadline em texto amigável com dias restantes."""
    if not deadline:
        return ""
    from datetime import date
    try:
        dl = date.fromisoformat(deadline)
        today = date.today()
        diff = (dl - today).days
        if diff < 0:
            return f" ⚠️ vencida há {abs(diff)}d"
        elif diff == 0:
            return " 🔥 vence hoje"
        elif diff == 1:
            return " ⏰ vence amanhã"
        else:
            return f" ({diff}d)"
    except Exception:
        return f" ({deadline})"


def format_daily_summary(tasks: list, notes: list, ideas: list) -> str:
    """Monta o resumo diário para envio pelo Telegram."""
    from datetime import date
    today = date.today().strftime("%d/%m/%Y")

    lines = [f"📅 *Resumo do dia — {today}*\n"]

    # Tarefas agrupadas por prioridade
    priority_order = ["critica", "urgente", "normal"]
    priority_titles = {
        "critica": "🔴 Críticas",
        "urgente": "🟠 Urgentes",
        "normal": "⚪ Normais",
    }

    tasks_by_priority = {p: [] for p in priority_order}
    for t in tasks:
        p = t.get("priority", "normal")
        if p in tasks_by_priority:
            tasks_by_priority[p].append(t)

    has_tasks = any(tasks_by_priority[p] for p in priority_order)
    if has_tasks:
        lines.append("*📋 Tarefas ativas:*")
        for p in priority_order:
            group = tasks_by_priority[p]
            if not group:
                continue
            lines.append(f"\n{priority_titles[p]}:")
            for t in group:
                name = t.get("name", "")
                deadline_str = _fmt_deadline(t.get("deadline"))
                project = f" [{t['project']}]" if t.get("project") else ""
                lines.append(f"  • {name}{project}{deadline_str}")
    else:
        lines.append("✨ Nenhuma tarefa ativa no momento.")

    # Notas recentes (últimas 5)
    if notes:
        lines.append(f"\n*📝 Notas recentes ({min(len(notes), 5)}):*")
        for n in notes[:5]:
            content = n.get("content", "")
            preview = content[:70] + "…" if len(content) > 70 else content
            lines.append(f"  • {preview}")

    # Ideias recentes (últimas 5)
    if ideas:
        lines.append(f"\n*💡 Ideias ({min(len(ideas), 5)}):*")
        for i in ideas[:5]:
            title = i.get("title", "")
            project = f" [{i['project']}]" if i.get("project") else ""
            lines.append(f"  • {title}{project}")

    # Rodapé com contagem
    lines.append(f"\n—\n📊 *{len(tasks)} ativa(s)*")

    return "\n".join(lines)
