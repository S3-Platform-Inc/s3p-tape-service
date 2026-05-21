from __future__ import annotations

import json
import logging
import os
from contextlib import asynccontextmanager

import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .api.auth import router as auth_router
from .api.config import router as config_router
from .api.health import router as health_router
from .api.tape import router as tape_router
from .api.ws import router as ws_router
from .db import close_pool, open_pool
from .errors import ApiError, api_error_handler
from .logging_setup import configure_logging
from .settings import get_settings
from .store import close_redis, open_redis
from .store.async_client import close_async_redis, open_async_redis

log = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(_app: FastAPI):
    s = get_settings()
    configure_logging(s.log_level)
    open_pool()
    open_redis()
    await open_async_redis()
    log.info("api.startup")
    try:
        yield
    finally:
        await close_async_redis()
        close_redis()
        close_pool()
        log.info("api.shutdown")


def _cors_allow_origins_from_env() -> list[str]:
    # Read directly from env so create_app() stays a pure constructor and
    # doesn't trip Settings validation in environments without DB/Redis/
    # session secret (e.g. the docker build's smoke test, which imports
    # this module to confirm the app instantiates).
    raw = os.environ.get("CORS_ALLOW_ORIGINS", "").strip()
    if not raw:
        return []
    try:
        v = json.loads(raw)
    except json.JSONDecodeError:
        return []
    if not isinstance(v, list):
        return []
    return [str(x) for x in v]


def create_app() -> FastAPI:
    app = FastAPI(title="S3 Platform Tape Service", version="0.1.0", lifespan=lifespan)
    # Only mount CORS when the deploy actually spans two domains. Empty
    # allowlist => same-origin deploy => no preflight overhead, no
    # accidental exposure. allow_credentials with credentials:'include'
    # requires an *exact* origin echo back; "*" is intentionally never used.
    origins = _cors_allow_origins_from_env()
    if origins:
        app.add_middleware(
            CORSMiddleware,
            allow_origins=origins,
            allow_credentials=True,
            allow_methods=["GET", "POST", "PUT", "OPTIONS"],
            allow_headers=["content-type"],
        )
    app.add_exception_handler(ApiError, api_error_handler)
    app.include_router(health_router)
    app.include_router(auth_router)
    app.include_router(config_router)
    app.include_router(tape_router)
    app.include_router(ws_router)
    return app


app = create_app()


def run() -> None:
    uvicorn.run("tape_service.main:app", host="0.0.0.0", port=8000, log_config=None)  # noqa: S104
