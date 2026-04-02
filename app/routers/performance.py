from fastapi import APIRouter, Request, Depends
from fastapi.responses import JSONResponse, RedirectResponse

from app.deps import get_current_user
from app.services.supabase_client import get_user_client

router = APIRouter()


@router.get("/performance/data")
async def performance_data(request: Request, user=Depends(get_current_user)):
    if isinstance(user, RedirectResponse):
        return JSONResponse({"error": "unauthenticated"}, status_code=401)

    client = get_user_client(user["access_token"], user["refresh_token"])

    active = (
        client.table("tasks").select("name, priority, project")
        .eq("user_id", user["user_id"])
        .eq("status", "active").execute().data or []
    )
    completed = (
        client.table("tasks").select("name, priority, project")
        .eq("user_id", user["user_id"])
        .eq("status", "completed").execute().data or []
    )

    def pri_counts(tasks):
        return {
            "critica": sum(1 for t in tasks if t.get("priority") == "critica"),
            "urgente": sum(1 for t in tasks if t.get("priority") == "urgente"),
            "normal":  sum(1 for t in tasks if t.get("priority") == "normal"),
        }

    # Tarefas com projeto: agrupa por projeto
    # Tarefas sem projeto: cada uma aparece com seu próprio nome
    all_tasks = active + completed
    project_names = sorted({t["project"] for t in all_tasks if t.get("project")})
    no_project_names = sorted({t.get("name", "Sem nome") for t in all_tasks if not t.get("project")})

    project_breakdown = []
    for proj in project_names:
        project_breakdown.append({
            "name": proj,
            "active": sum(1 for t in active if t.get("project") == proj),
            "completed": sum(1 for t in completed if t.get("project") == proj),
        })
    for task_name in no_project_names:
        project_breakdown.append({
            "name": task_name,
            "active": sum(1 for t in active if not t.get("project") and t.get("name") == task_name),
            "completed": sum(1 for t in completed if not t.get("project") and t.get("name") == task_name),
        })
    project_breakdown.sort(key=lambda x: x["active"] + x["completed"], reverse=True)

    return JSONResponse({
        "active_count": len(active),
        "completed_count": len(completed),
        "priority_breakdown": {
            "active": pri_counts(active),
            "completed": pri_counts(completed),
        },
        "project_breakdown": project_breakdown,
    })
