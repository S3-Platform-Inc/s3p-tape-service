from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel


class RoleRef(BaseModel):
    id: int
    name: str | None = None


class TapeDocument(BaseModel):
    id: int
    source_id: int
    title: str
    link: str
    published: datetime
    abstract: str | None = None
    # text is populated only when the user's display_mode is "detailed"
    text: str | None = None


class TapeItem(BaseModel):
    entry_id: int
    position: int
    document: TapeDocument
    roles: list[RoleRef]


class TapePage(BaseModel):
    items: list[TapeItem]
    next_position: int | None
    state: Literal["ok", "empty", "preparing"]
    display_mode: Literal["compact", "detailed"]
