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
        client.table("tasks").select("priority, project")
        .eq("user_id", user["user_id"])
        .eq("status", "active").execute().data or []
    )
    completed = (
        client.table("tasks").select("priority, project")
        .eq("user_id", user["user_id"])
        .eq("status", "completed").execute().data or []
    )

    def pri_counts(tasks):
        return {
            "critica": sum(1 for t in tasks if t.get("priority") == "critica"),
            "urgente": sum(1 for t in tasks if t.get("priority") == "urgente"),
            "normal":  sum(1 for t in tasks if t.get("priority") == "normal"),
        }

    all_projects = sorted({t.get("project") or "Sem projeto" for t in active + completed})
    project_breakdown = []
    for proj in all_projects:
        project_breakdown.append({
            "name": proj,
            "active": sum(1 for t in active if (t.get("project") or "Sem projeto") == proj),
            "completed": sum(1 for t in completed if (t.get("project") or "Sem projeto") == proj),
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
