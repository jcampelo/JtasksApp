from fastapi import APIRouter, Request, Depends, Form
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates

from app.deps import get_current_user
from app.services import approval_service
from app.services.approval_service import OWNER_EMAIL

router = APIRouter()
templates = Jinja2Templates(directory="app/templates")


def _require_owner(user):
    if user.get("email") != OWNER_EMAIL:
        return HTMLResponse("Acesso negado.", status_code=403)
    return None


@router.get("/admin", response_class=HTMLResponse)
async def admin_tab(request: Request, user=Depends(get_current_user)):
    if isinstance(user, RedirectResponse):
        return user
    gate = _require_owner(user)
    if gate:
        return gate

    approvals = approval_service.list_all()
    return templates.TemplateResponse(
        "partials/admin/admin_tab.html",
        {"request": request, "approvals": approvals},
    )


@router.post("/admin/approve", response_class=HTMLResponse)
async def approve(request: Request, user_id: str = Form(...), user=Depends(get_current_user)):
    if isinstance(user, RedirectResponse):
        return user
    gate = _require_owner(user)
    if gate:
        return gate

    approval_service.set_status(user_id, "approved", approved_by=user["user_id"])
    approvals = approval_service.list_all()
    return templates.TemplateResponse(
        "partials/admin/admin_tab.html",
        {"request": request, "approvals": approvals},
    )


@router.post("/admin/reject", response_class=HTMLResponse)
async def reject(request: Request, user_id: str = Form(...), user=Depends(get_current_user)):
    if isinstance(user, RedirectResponse):
        return user
    gate = _require_owner(user)
    if gate:
        return gate

    approval_service.set_status(user_id, "rejected", approved_by=user["user_id"])
    approvals = approval_service.list_all()
    return templates.TemplateResponse(
        "partials/admin/admin_tab.html",
        {"request": request, "approvals": approvals},
    )
