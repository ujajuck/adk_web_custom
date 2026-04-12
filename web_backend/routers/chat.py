"""Chat endpoint - proxy to ADK backend."""

from __future__ import annotations

import json
import logging
import uuid
from pathlib import Path

from fastapi import APIRouter, HTTPException

from ..config import settings
from ..database import get_db
from ..models import ChatRequest, ChatResponse, CsvFileMeta, OutputItem, PlotlyFigMeta
from ..services.adk_client import send_message_to_adk
from ..services.csv_store import csv_store
from ..services.plotly_store import plotly_store
from ..services.response_parser import (
    extract_artifact_delta,
    extract_assistant_text,
    extract_frontend_trigger,
    extract_plotly_fig,
    extract_plotly_urls,
    extract_resource_links_from_events,
    extract_responding_agent,
)
from ..services.plotly_fetcher import fetch_plotly_from_url
from ..services.flow_parser import parse_artifact_flow
from ..services.flow_store import flow_store
from ..services.flow_db import save_flow_edges

router = APIRouter(prefix="/api/chat", tags=["chat"])
log = logging.getLogger(__name__)


def _resolve_artifact_path(
    user_id: str, session_id: str, filename: str, version: int
) -> Path:
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
    log.info("Chat request: user=%s session=%s msg=%s", req.user_id, req.session_id, req.message[:100])
    job_id = f"job_{uuid.uuid4().hex[:12]}"

    try:
        adk_result = await send_message_to_adk(
            req.user_id, req.session_id, req.message, req.agent_name
        )
        log.debug("ADK returned status=%s", adk_result.get("status"))
    except Exception as exc:
        log.error("ADK request failed: %s", exc, exc_info=True)
        raise HTTPException(502, detail=f"ADK request failed: {exc}")

    if adk_result.get("status") == "error":
        error_msg = adk_result.get("error", "Unknown ADK error")
        log.warning("ADK returned error: %s", error_msg)
        raise HTTPException(502, detail=f"ADK error: {error_msg}")

    events = adk_result.get("events", [])
    outputs = adk_result.get("outputs", [])
    log.debug("ADK returned %d events, %d outputs", len(events), len(outputs))

    assistant_text = extract_assistant_text(events)
    artifact_delta = extract_artifact_delta(events)
    plotly_result = extract_plotly_fig(events)
    responding_agent = extract_responding_agent(events)
    frontend_data = extract_frontend_trigger(events)

    csv_metas: list[CsvFileMeta] = []
    plotly_metas: list[PlotlyFigMeta] = []

    for filename, version in artifact_delta.items():
        file_id = f"{req.session_id}__{filename}__v{version}"
        artifact_path = _resolve_artifact_path(
            req.user_id, req.session_id, filename, version
        )

        if not artifact_path.exists():
            log.warning("Artifact path does not exist: %s", artifact_path)
            continue

        if filename.lower().endswith(".csv"):
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
                log.info("Loaded CSV artifact: %s (%d rows)", filename, len(df))
            except Exception as exc:
                log.warning("Failed to load CSV %s: %s", filename, exc)

        elif filename.lower().endswith(".json"):
            try:
                raw_content = artifact_path.read_text(encoding="utf-8")
                fig_data = json.loads(raw_content)
                if isinstance(fig_data, str):
                    fig_data = json.loads(fig_data)
                fig_id = f"{req.session_id}__fig__{uuid.uuid4().hex[:8]}"
                title = filename.replace(".json", "")
                plotly_store.store(fig_id, title, fig_data)
                plotly_metas.append(
                    PlotlyFigMeta(
                        fig_id=fig_id,
                        title=title,
                        fig=fig_data,
                    )
                )
                log.info("Loaded Plotly figure from artifact: %s", filename)
            except Exception as exc:
                log.warning("Failed to load JSON artifact %s: %s", filename, exc)

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

    resource_link_urls = extract_resource_links_from_events(events)
    text_urls = extract_plotly_urls(assistant_text)
    output_urls = [
        o.get("uri") for o in outputs
        if isinstance(o, dict) and o.get("type") == "resource_link" and o.get("uri")
    ]
    plotly_urls = list(dict.fromkeys(resource_link_urls + output_urls + text_urls))

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

    try:
        existing_flow = flow_store.get(req.session_id)
        prev_edge_ids = {e.id for e in existing_flow.edges} if existing_flow else set()
        updated_flow = parse_artifact_flow(
            session_id=req.session_id,
            events=events,
            artifact_delta=artifact_delta,
            existing_flow=existing_flow,
        )
        flow_store.update(req.session_id, updated_flow)
        log.debug("Flow updated: %d nodes, %d edges", len(updated_flow.nodes), len(updated_flow.edges))
        # 새 엣지만 DB에 저장
        new_edges = [e for e in updated_flow.edges if e.id not in prev_edge_ids]
        if new_edges:
            await save_flow_edges(req.session_id, new_edges, updated_flow.nodes)
    except Exception as exc:
        log.warning("Failed to parse artifact flow: %s", exc)

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

    output_items = [
        OutputItem(
            type=o.get("type", ""),
            uri=o.get("uri", ""),
            mime_type=o.get("mime_type", ""),
        )
        for o in outputs
        if isinstance(o, dict) and o.get("type") and o.get("uri")
    ]

    return ChatResponse(
        job_id=job_id,
        status="success",
        text=assistant_text,
        responding_agent=responding_agent,
        frontend_data=frontend_data,
        outputs=output_items,
        csv_files=csv_metas,
        plotly_figs=plotly_metas,
    )
