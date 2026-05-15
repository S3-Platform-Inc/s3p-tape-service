from __future__ import annotations

from pydantic import BaseModel, Field


class LoginRequest(BaseModel):
    token: str = Field(min_length=8, max_length=512)


class MeResponse(BaseModel):
    user_id: int
