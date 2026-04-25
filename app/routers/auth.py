import os

from fastapi import APIRouter, Request, Form
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from supabase import create_client

from app.config import settings
from app.services import approval_service
from app.services import session_service

router = APIRouter()
templates = Jinja2Templates(directory="app/templates")

try:
    _css_path = os.path.join(os.path.dirname(__file__), "..", "..", "static", "css", "app.css")
    _CSS_V = str(int(os.path.getmtime(_css_path)))
except OSError:
    _CSS_V = "1"


@router.api_route("/auth/login", methods=["GET", "HEAD"], response_class=HTMLResponse)
async def login_page(request: Request):
    if request.session.get("session_id"):
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

        if not approval_service.is_approved(str(user.id), user.email):
            status = approval_service.get_status(str(user.id))
            if status is None:
                # O usuário efetuou o cadastro antes do sistema de aprovação existir.
                # Criamos a solicitação de aprovação agora.
                approval_service.create_pending(str(user.id), user.email)
                error_msg = "Sua conta estava inativa e agora foi enviada para aprovação do administrador."
            elif status == "rejected":
                error_msg = "Seu cadastro foi recusado. Entre em contato com o administrador."
            else:
                error_msg = "Sua conta está aguardando aprovação do administrador."
            return templates.TemplateResponse(
                "login.html",
                {"request": request, "error": error_msg, "css_version": _CSS_V},
                status_code=200,
            )

        session_id = session_service.create_session(
            user_id=str(user.id),
            email=user.email,
            access_token=session_data.access_token,
            refresh_token=session_data.refresh_token,
            expires_at=session_data.expires_at,
        )
        request.session["session_id"] = session_id

        # HTMX: redireciona via header
        response = HTMLResponse(content="", status_code=200)
        response.headers["HX-Redirect"] = "/app"
        return response

    except Exception as e:
        print(f"[LOGIN DEBUG] Exception type: {type(e).__name__}, message: {e}")
        error_msg = "Email ou senha incorretos."
        if "Invalid login" in str(e) or "invalid" in str(e).lower():
            error_msg = "Email ou senha incorretos."
        return templates.TemplateResponse(
            "login.html",
            {"request": request, "error": error_msg, "css_version": _CSS_V},
            status_code=200,
        )


@router.post("/auth/logout")
async def logout(request: Request):
    session_id = request.session.get("session_id")
    if session_id:
        session_service.delete_session(session_id)
    request.session.clear()
    return RedirectResponse(url="/auth/login", status_code=302)


@router.get("/register", response_class=HTMLResponse)
async def register_page(request: Request):
    if request.session.get("session_id"):
        return RedirectResponse(url="/app", status_code=302)
    return templates.TemplateResponse("register.html", {"request": request, "error": None, "success": False, "css_version": _CSS_V})


@router.post("/register", response_class=HTMLResponse)
async def register_submit(
    request: Request,
    email: str = Form(...),
    password: str = Form(...),
):
    try:
        client = create_client(settings.supabase_url, settings.supabase_anon_key)
        result = client.auth.sign_up({"email": email, "password": password})

        # Registra solicitação de aprovação (owner é auto-aprovado)
        user = result.user
        if user:
            approval_service.create_pending(str(user.id), user.email or email)

        # Nunca cria sessão aqui — usuário precisa ser aprovado e fazer login.
        return templates.TemplateResponse(
            "register.html",
            {"request": request, "error": None, "success": True, "css_version": _CSS_V},
        )

    except Exception as e:
        error_msg = "Não foi possível criar a conta."
        if "already registered" in str(e).lower() or "already been registered" in str(e).lower():
            error_msg = "Este email já está cadastrado."
        return templates.TemplateResponse(
            "register.html",
            {"request": request, "error": error_msg, "success": False, "css_version": _CSS_V},
            status_code=200,
        )
