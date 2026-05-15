from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


class SourceRef(BaseModel):
    id: int
    name: str | None = None


class ConfigResponse(BaseModel):
    ordering: Literal["asc", "desc"]
    display_mode: Literal["compact", "detailed"]
    page_size: int
    date_from: datetime | None
    date_to: datetime | None
    dirty: bool
    selected_source_ids: list[int]
    available_sources: list[SourceRef]


class ConfigUpdate(BaseModel):
    ordering: Literal["asc", "desc"]
    display_mode: Literal["compact", "detailed"]
    page_size: int = Field(ge=1, le=200)
    date_from: datetime | None = None
    date_to: datetime | None = None
    selected_source_ids: list[int] = Field(default_factory=list)
