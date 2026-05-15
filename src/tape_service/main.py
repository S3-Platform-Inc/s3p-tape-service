from __future__ import annotations

import logging
from contextlib import asynccontextmanager

import uvicorn
from fastapi import FastAPI

from .api.auth import router as auth_router
from .api.config import router as config_router
from .api.health import router as health_router
from .api.tape import router as tape_router
from .db import close_pool, open_pool
from .errors import ApiError, api_error_handler
from .logging_setup import configure_logging
from .settings import get_settings
from .store import close_redis, open_redis

log = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(_app: FastAPI):
    s = get_settings()
    configure_logging(s.log_level)
    open_pool()
    open_redis()
    log.info("api.startup")
    try:
        yield
    finally:
        close_redis()
        close_pool()
        log.info("api.shutdown")


def create_app() -> FastAPI:
    app = FastAPI(title="S3 Platform Tape Service", version="0.1.0", lifespan=lifespan)
    app.add_exception_handler(ApiError, api_error_handler)
    app.include_router(health_router)
    app.include_router(auth_router)
    app.include_router(config_router)
    app.include_router(tape_router)
    return app


app = create_app()


def run() -> None:
    uvicorn.run("tape_service.main:app", host="0.0.0.0", port=8000, log_config=None)  # noqa: S104
