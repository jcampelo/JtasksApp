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
