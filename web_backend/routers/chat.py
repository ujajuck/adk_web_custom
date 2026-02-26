"""Chat endpoint – proxies to ADK, parses response, stores results."""

from __future__ import annotations

import json
import logging
import uuid
from pathlib import Path

from fastapi import APIRouter, HTTPException

from ..config import settings
from ..database import get_db
from ..models import ChatRequest, ChatResponse, CsvFileMeta, PlotlyFigMeta
from ..services.adk_client import send_message_to_adk
from ..services.csv_store import csv_store
from ..services.plotly_store import plotly_store
from ..services.response_parser import (
    extract_artifact_delta,
    extract_assistant_text,
    extract_plotly_fig,
    extract_plotly_urls,
)
from ..services.plotly_fetcher import fetch_plotly_from_url
from ..services.flow_parser import parse_artifact_flow
from ..services.flow_store import flow_store

router = APIRouter(prefix="/api/chat", tags=["chat"])
log = logging.getLogger(__name__)


def _resolve_artifact_path(
    user_id: str, session_id: str, filename: str, version: int
) -> Path:
    """Build the filesystem path to an ADK artifact."""
    root = Path(settings.ADK_ARTIFACT_ROOT)
    return (
        root
        / "users"
        / user_id
        / "sessions"
        / session_id
        / "artifacts"
        / filename
        / "versions"
        / str(version)
        / filename
    )


@router.post("", response_model=ChatResponse)
async def chat(req: ChatRequest):
    """Send a user message to ADK, parse the response, and persist."""
    log.info("Chat request: user=%s session=%s msg=%s", req.user_id, req.session_id, req.message[:100])
    job_id = f"job_{uuid.uuid4().hex[:12]}"

    # 1. Forward to ADK
    try:
        events = await send_message_to_adk(req.user_id, req.session_id, req.message)
        log.debug("ADK returned %d events", len(events))
    except Exception as exc:
        log.error("ADK request failed: %s", exc, exc_info=True)
        raise HTTPException(502, detail=f"ADK request failed: {exc}")

    # 2. Parse response
    assistant_text = extract_assistant_text(events)
    artifact_delta = extract_artifact_delta(events)
    plotly_result = extract_plotly_fig(events)

    # 3. Process CSV artifacts
    csv_metas: list[CsvFileMeta] = []
    for filename, version in artifact_delta.items():
        file_id = f"{req.session_id}__{filename}__v{version}"
        artifact_path = _resolve_artifact_path(
            req.user_id, req.session_id, filename, version
        )

        if artifact_path.exists():
            try:
                df = csv_store.store_from_path(file_id, artifact_path, filename)
                csv_metas.append(
                    CsvFileMeta(
                        file_id=file_id,
                        filename=filename,
                        total_rows=len(df),
                        total_cols=len(df.columns),
                        columns=list(df.columns),
                    )
                )
            except Exception as exc:
                log.warning("Failed to load CSV %s: %s", filename, exc)
        else:
            log.warning("Artifact path does not exist: %s", artifact_path)

    # 4. Process plotly figure (embedded in events)
    plotly_metas: list[PlotlyFigMeta] = []
    if plotly_result:
        fig_id = f"{req.session_id}__fig__{uuid.uuid4().hex[:8]}"
        plotly_store.store(fig_id, plotly_result["title"], plotly_result["fig"])
        plotly_metas.append(
            PlotlyFigMeta(
                fig_id=fig_id,
                title=plotly_result["title"],
                fig=plotly_result["fig"],
            )
        )

    # 4b. Process plotly URLs (MCP resource links in assistant text)
    plotly_urls = extract_plotly_urls(assistant_text)
    for url in plotly_urls:
        try:
            fetched = await fetch_plotly_from_url(url)
            if fetched:
                fig_id = f"{req.session_id}__fig__{uuid.uuid4().hex[:8]}"
                plotly_store.store(fig_id, fetched["title"], fetched["fig"])
                plotly_metas.append(
                    PlotlyFigMeta(
                        fig_id=fig_id,
                        title=fetched["title"],
                        fig=fetched["fig"],
                    )
                )
                log.info("Added Plotly figure from URL: %s", url)
        except Exception as exc:
            log.warning("Failed to fetch Plotly from URL %s: %s", url, exc)

    # 5. Parse and store artifact flow
    try:
        existing_flow = flow_store.get(req.session_id)
        updated_flow = parse_artifact_flow(
            session_id=req.session_id,
            events=events,
            artifact_delta=artifact_delta,
            existing_flow=existing_flow,
        )
        flow_store.update(req.session_id, updated_flow)
        log.debug("Flow updated: %d nodes, %d edges", len(updated_flow.nodes), len(updated_flow.edges))
    except Exception as exc:
        log.warning("Failed to parse artifact flow: %s", exc)

    # 6. Persist to SQLite
    db = await get_db()
    try:
        await db.execute(
            """INSERT INTO chat_jobs
               (user_id, session_id, job_id, request_message, response_text, csv_meta, plotly_meta)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (
                req.user_id,
                req.session_id,
                job_id,
                req.message,
                assistant_text,
                json.dumps([m.model_dump() for m in csv_metas], ensure_ascii=False),
                json.dumps([m.model_dump() for m in plotly_metas], ensure_ascii=False),
            ),
        )
        await db.commit()
    finally:
        await db.close()

    return ChatResponse(
        job_id=job_id,
        text=assistant_text,
        csv_files=csv_metas,
        plotly_figs=plotly_metas,
    )
