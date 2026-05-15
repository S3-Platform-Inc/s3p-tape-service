from __future__ import annotations
import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI
import uvicorn

from .api.health import router as health_router
from .db import close_pool, open_pool
from .errors import ApiError, api_error_handler
from .logging_setup import configure_logging
from .settings import get_settings

log = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(_app: FastAPI):
    s = get_settings()
    configure_logging(s.log_level)
    open_pool()
    log.info("api.startup")
    try:
        yield
    finally:
        close_pool()
        log.info("api.shutdown")


def create_app() -> FastAPI:
    app = FastAPI(title="S3 Platform Tape Service", version="0.1.0", lifespan=lifespan)
    app.add_exception_handler(ApiError, api_error_handler)
    app.include_router(health_router)
    return app


app = create_app()


def run() -> None:
    uvicorn.run("tape_service.main:app", host="0.0.0.0", port=8000, log_config=None)
