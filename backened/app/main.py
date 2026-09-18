import logging
import os

from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from openai import RateLimitError
from app.api.endpoints import chat
from app.db.database import engine, Base
from fastapi.staticfiles import StaticFiles
from app.db import models   # noqa: F401 — ensures models are registered before create_all
from app.routers import auth, tasks, requests, users, notifications, skill_engine, assistant, support

logger = logging.getLogger(__name__)

# Creates any tables that don't already exist in SQL Server.
# Existing tables are left untouched — new columns need a manual ALTER TABLE.
Base.metadata.create_all(bind=engine)

app = FastAPI(title="BRAINOPX Configuration Assistant API")

# ─── CORS Configuration ────────────────────────────────────────────────
# In production, set CORS_ORIGINS env var to a comma-separated list of allowed origins.
# In development, a broad set of common dev server origins is allowed.
_default_origins = [
    "http://localhost:5173",
    "http://127.0.0.1:5173",
    "http://localhost:5174",
    "http://127.0.0.1:5174",
    "http://localhost:5175",
    "http://127.0.0.1:5175",
    "http://localhost:5176",
    "http://127.0.0.1:5176",
    "http://localhost:5177",
    "http://127.0.0.1:5177",
    "http://localhost:8080",
    "http://localhost:3000",
]

_env_origins = os.getenv("CORS_ORIGINS")
if _env_origins:
    allowed_origins = [o.strip() for o in _env_origins.split(",") if o.strip()]
else:
    allowed_origins = _default_origins

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)
app.include_router(tasks.router)
app.include_router(requests.router)
app.include_router(users.router)
app.include_router(notifications.router)
app.include_router(skill_engine.router)
app.include_router(assistant.router)
app.include_router(support.router)
app.include_router(chat.router, prefix="/api")


@app.exception_handler(RateLimitError)
async def groq_rate_limit_handler(request: Request, exc: RateLimitError):
    # Any endpoint that calls into groq_service can hit Groq's per-minute
    # or per-day token cap; groq_service's own retry loop already exhausts
    # the cases it can recover from, so anything that reaches here is not
    # worth retrying. Surface it as a clean 503 instead of a 500 crash.
    logger.warning("Groq rate limit reached on %s: %s", request.url.path, exc)
    return JSONResponse(
        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        content={"detail": "The AI service is temporarily unavailable due to high demand. Please try again in a few minutes."},
    )

# Serve uploaded files
app.mount("/uploads", StaticFiles(directory="uploads"), name="uploads")

@app.get("/health")
def health_check():
    return {"status": "ok"}
