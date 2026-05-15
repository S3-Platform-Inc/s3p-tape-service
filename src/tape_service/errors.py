from __future__ import annotations

from enum import Enum

from fastapi import Request
from fastapi.responses import JSONResponse


class ErrorCode(Enum):
    INVALID_REQUEST = (400, "INVALID_REQUEST")
    UNAUTHORIZED = (401, "UNAUTHORIZED")
    FORBIDDEN = (403, "FORBIDDEN")
    NOT_FOUND = (404, "NOT_FOUND")
    CONFLICT = (409, "CONFLICT")
    ALREADY_SCORED = (409, "ALREADY_SCORED")
    RATE_LIMITED = (429, "RATE_LIMITED")
    TAPE_PREPARING = (503, "TAPE_PREPARING")
    INTERNAL = (500, "INTERNAL")

    def __init__(self, status: int, code: str) -> None:
        self.status = status
        self.code = code


class ApiError(Exception):
    def __init__(self, code: ErrorCode, message: str = "") -> None:
        self.code = code
        self.message = message or code.code
        super().__init__(self.message)

    @property
    def status_code(self) -> int:
        return self.code.status

    def to_dict(self) -> dict:
        return {"error": {"code": self.code.code, "message": self.message}}


async def api_error_handler(_request: Request, exc: ApiError) -> JSONResponse:
    return JSONResponse(exc.to_dict(), status_code=exc.status_code)
