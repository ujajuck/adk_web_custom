from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


# ── Requests ──────────────────────────────────────────────


class SessionCreateRequest(BaseModel):
    user_id: str
    session_id: str
    session_name: str = ""
    state: dict[str, Any] = Field(default_factory=dict)


class ChatRequest(BaseModel):
    user_id: str
    session_id: str
    message: str
    agent_name: str | None = None


# ── Responses ─────────────────────────────────────────────


class SessionInfo(BaseModel):
    session_id: str
    user_id: str
    session_name: str
    created_at: str
    expired: bool


class CsvFileMeta(BaseModel):
    file_id: str
    filename: str
    total_rows: int
    total_cols: int
    columns: list[str]


class PlotlyFigMeta(BaseModel):
    fig_id: str
    title: str
    fig: dict[str, Any]


class OutputItem(BaseModel):
    type: str
    uri: str
    mime_type: str = ""


class ChatResponse(BaseModel):
    job_id: str
    status: str = "success"
    text: str
    responding_agent: str = "root_agent"
    outputs: list[OutputItem] = Field(default_factory=list)
    # Legacy fields (deprecated)
    csv_files: list[CsvFileMeta] = Field(default_factory=list)
    plotly_figs: list[PlotlyFigMeta] = Field(default_factory=list)
    raw_events: Any | None = None


class CsvPageResponse(BaseModel):
    file_id: str
    filename: str
    columns: list[str]
    rows: list[dict[str, Any]]
    total_rows: int
    offset: int
    limit: int
