"""
JtasksApp - Gerenciador de Tarefas Corporativo Multi-tenant

Entry point da aplicação FastAPI.
Responsável por:
  - Inicializar a aplicação FastAPI
  - Gerenciar middleware de sessão (autenticação)
  - Servir arquivos estáticos (CSS, JS)
  - Registrar todos os routers (endpoints)
  - Iniciar e parar o agendador de jobs (APScheduler)
"""

from contextlib import asynccontextmanager
import uvicorn
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from starlette.middleware.sessions import SessionMiddleware

from app.config import settings
from app.routers import auth, app_router, tasks, projects, presets, performance, notify, export, ideas
from app.scheduler import start_scheduler, stop_scheduler


# Gerenciador de ciclo de vida da aplicação (startup/shutdown)
# Inicia o scheduler quando a app sobe e para quando desce
@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Controla eventos de inicialização e encerramento da aplicação.

    - Ao iniciar: Ativa o APScheduler (jobs de email diário)
    - Ao encerrar: Para o scheduler para liberar recursos
    """
    start_scheduler()
    yield  # App rodando enquanto yielda
    stop_scheduler()


# Instancia a aplicação FastAPI com gerenciador de ciclo de vida
app = FastAPI(title="Jtasks", lifespan=lifespan)

# Middleware de sessão: permite armazenar dados do usuário em request.session
# https_only=False para desenvolvimento; em produção usar True
app.add_middleware(SessionMiddleware, secret_key=settings.secret_key, https_only=False)

# Serve arquivos estáticos (CSS, JavaScript, imagens) da pasta /static
app.mount("/static", StaticFiles(directory="static"), name="static")

# ===== Registra todos os routers (conjuntos de endpoints) =====
# Cada router está em um arquivo separado para melhor organização
app.include_router(auth.router)           # POST /auth/login, POST /auth/logout
app.include_router(app_router.router)     # GET /, GET /app (página principal)
app.include_router(tasks.router)          # CRUD de tarefas, filtros, updates, checklist
app.include_router(projects.router)       # CRUD de projetos
app.include_router(presets.router)        # Templates de tarefas (presets)
app.include_router(performance.router)    # Dados para gráficos de produtividade
app.include_router(notify.router)         # Configurar notificações por email
app.include_router(export.router)         # Exportar tarefas em Excel
app.include_router(ideas.router)          # Mural de ideias de projetos


# Inicia servidor apenas se o arquivo for executado diretamente
if __name__ == "__main__":
    # Inicia Uvicorn (servidor ASGI) em 0.0.0.0:8000 (ou porta configurada)
    # reload=True: reinicia app automaticamente quando há mudanças de código (desenvolvimento)
    uvicorn.run("main:app", host="0.0.0.0", port=settings.port, reload=True)
