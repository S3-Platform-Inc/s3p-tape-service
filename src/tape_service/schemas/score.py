from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class ScoreRequest(BaseModel):
    document_id: int
    role_id: int
    verdict: Literal["yes", "no", "unsure"]
    comment: str | None = Field(default=None, max_length=2000)
