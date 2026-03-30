from fastapi import APIRouter, Request, Depends
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates

from app.deps import get_current_user

router = APIRouter()
templates = Jinja2Templates(directory="app/templates")


@router.api_route("/", methods=["GET", "HEAD"], response_class=HTMLResponse)
async def root(request: Request):
    if request.session.get("user"):
        return RedirectResponse(url="/app", status_code=302)
    return RedirectResponse(url="/auth/login", status_code=302)


@router.get("/app", response_class=HTMLResponse)
async def app_page(request: Request, user=Depends(get_current_user)):
    if isinstance(user, RedirectResponse):
        return user
    return templates.TemplateResponse("pages/app.html", {"request": request, "user": user})
