"""FastAPI для Mini App BTF: задачи, отчёты, команда, чаты, модерация, пересылка, настройки."""
from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from api.deps import get_bot
from api.routers import boards, chats, relay, reports, settings, tasks, team
from bot.services.series import SeriesError
from bot.services.tasks import TaskError


@asynccontextmanager
async def lifespan(app: FastAPI):
    yield
    await get_bot().session.close()


app = FastAPI(title="BTF Mini App API", lifespan=lifespan, docs_url=None, redoc_url=None)
# В проде фронт и API под одним доменом (Caddy); CORS — для локального vite dev.
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])


@app.exception_handler(TaskError)
@app.exception_handler(SeriesError)
async def domain_error(request: Request, exc: Exception) -> JSONResponse:
    return JSONResponse({"detail": str(exc)}, status_code=400)


@app.get("/api/health")
async def health() -> dict:
    return {"ok": True}


for module in (team, boards, tasks, reports, chats, relay, settings):
    app.include_router(module.router)
