from contextlib import asynccontextmanager
import uvicorn
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from starlette.middleware.sessions import SessionMiddleware

from app.config import settings
from app.routers import auth, app_router, tasks, projects, presets, performance, notify, export, ideas
from app.scheduler import start_scheduler, stop_scheduler


@asynccontextmanager
async def lifespan(app: FastAPI):
    start_scheduler()
    yield
    stop_scheduler()


app = FastAPI(title="Jtasks", lifespan=lifespan)

app.add_middleware(SessionMiddleware, secret_key=settings.secret_key, https_only=False)
app.mount("/static", StaticFiles(directory="static"), name="static")

app.include_router(auth.router)
app.include_router(app_router.router)
app.include_router(tasks.router)
app.include_router(projects.router)
app.include_router(presets.router)
app.include_router(performance.router)
app.include_router(notify.router)
app.include_router(export.router)
app.include_router(ideas.router)


if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=settings.port, reload=True)
