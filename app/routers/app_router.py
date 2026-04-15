import os

from fastapi import APIRouter, Request, Depends
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates

from app.deps import get_current_user
from app.services.supabase_client import get_user_client
from app.services.approval_service import OWNER_EMAIL

router = APIRouter()
templates = Jinja2Templates(directory="app/templates")

try:
    _css_path = os.path.join(os.path.dirname(__file__), "..", "..", "static", "css", "app.css")
    _CSS_V = str(int(os.path.getmtime(_css_path)))
except OSError:
    _CSS_V = "1"


@router.api_route("/", methods=["GET", "HEAD"], response_class=HTMLResponse)
async def root(request: Request):
    if request.session.get("user"):
        return RedirectResponse(url="/app", status_code=302)
    return RedirectResponse(url="/auth/login", status_code=302)


@router.get("/app", response_class=HTMLResponse)
async def app_page(request: Request, user=Depends(get_current_user)):
    if isinstance(user, RedirectResponse):
        return user

    try:
        client = get_user_client(user["access_token"], user["refresh_token"])
        prefs = client.table("user_preferences") \
            .select("theme") \
            .eq("user_id", user["user_id"]) \
            .execute()
        user_theme = prefs.data[0]["theme"] if prefs.data else "dark"
    except Exception:
        user_theme = "dark"

    return templates.TemplateResponse(
        "pages/app.html",
        {"request": request, "user": user, "css_version": _CSS_V, "user_theme": user_theme, "owner_email": OWNER_EMAIL},
    )
