from fastapi import APIRouter, Request, Depends
from fastapi.responses import JSONResponse, RedirectResponse

from app.deps import get_current_user
from app.services.supabase_client import get_user_client

router = APIRouter()


@router.post("/user/theme")
async def save_theme(request: Request, user=Depends(get_current_user)):
    if isinstance(user, RedirectResponse):
        return user

    body = await request.json()
    theme = body.get("theme", "light")
    if theme not in ("light", "dark"):
        return JSONResponse({"ok": False, "error": "invalid theme"}, status_code=400)

    client = get_user_client(user["access_token"], user["refresh_token"])
    client.table("user_preferences").upsert(
        {"user_id": user["user_id"], "theme": theme}
    ).execute()

    return JSONResponse({"ok": True})
