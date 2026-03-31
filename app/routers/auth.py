import os

from fastapi import APIRouter, Request, Form
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from supabase import create_client

from app.config import settings

router = APIRouter()
templates = Jinja2Templates(directory="app/templates")

try:
    _css_path = os.path.join(os.path.dirname(__file__), "..", "..", "static", "css", "app.css")
    _CSS_V = str(int(os.path.getmtime(_css_path)))
except OSError:
    _CSS_V = "1"


@router.api_route("/auth/login", methods=["GET", "HEAD"], response_class=HTMLResponse)
async def login_page(request: Request):
    if request.session.get("user"):
        return RedirectResponse(url="/app", status_code=302)
    return templates.TemplateResponse("login.html", {"request": request, "error": None, "css_version": _CSS_V})


@router.post("/auth/login", response_class=HTMLResponse)
async def login_submit(
    request: Request,
    email: str = Form(...),
    password: str = Form(...),
):
    try:
        client = create_client(settings.supabase_url, settings.supabase_anon_key)
        result = client.auth.sign_in_with_password({"email": email, "password": password})
        session_data = result.session
        user = result.user

        request.session["user"] = {
            "access_token": session_data.access_token,
            "refresh_token": session_data.refresh_token,
            "expires_at": session_data.expires_at,
            "user_id": str(user.id),
            "email": user.email,
        }

        # HTMX: redireciona via header
        response = HTMLResponse(content="", status_code=200)
        response.headers["HX-Redirect"] = "/app"
        return response

    except Exception as e:
        error_msg = "Email ou senha incorretos."
        if "Invalid login" in str(e) or "invalid" in str(e).lower():
            error_msg = "Email ou senha incorretos."
        return templates.TemplateResponse(
            "login.html",
            {"request": request, "error": error_msg, "css_version": _CSS_V},
            status_code=401,
        )


@router.post("/auth/logout")
async def logout(request: Request):
    request.session.clear()
    return RedirectResponse(url="/auth/login", status_code=302)
