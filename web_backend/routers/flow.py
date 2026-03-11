"""Flow API – artifact flow graph endpoints."""

from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from ..services.flow_store import flow_store

router = APIRouter(prefix="/api/flow", tags=["flow"])
log = logging.getLogger(__name__)


class FlowResponse(BaseModel):
    """아티팩트 흐름 응답."""
    session_id: str
    nodes: list[dict[str, Any]]
    edges: list[dict[str, Any]]


class FlowSummary(BaseModel):
    """세션 플로우 요약."""
    session_id: str
    node_count: int
    edge_count: int


@router.get("/{session_id}", response_model=FlowResponse)
async def get_flow(session_id: str):
    """세션의 아티팩트 흐름 조회."""
    flow = flow_store.get(session_id)
    if not flow:
        # 빈 플로우 반환 (에러 대신)
        return FlowResponse(session_id=session_id, nodes=[], edges=[])

    return FlowResponse(
        session_id=flow.session_id,
        nodes=[n.to_dict() for n in flow.nodes],
        edges=[e.to_dict() for e in flow.edges],
    )


@router.get("", response_model=list[FlowSummary])
async def list_flows():
    """모든 세션의 플로우 요약 목록."""
    summaries = []
    for session_id in flow_store.list_sessions():
        flow = flow_store.get(session_id)
        if flow:
            summaries.append(FlowSummary(
                session_id=session_id,
                node_count=len(flow.nodes),
                edge_count=len(flow.edges),
            ))
    return summaries


@router.delete("/{session_id}")
async def delete_flow(session_id: str):
    """세션의 플로우 삭제."""
    deleted = flow_store.delete(session_id)
    return {"deleted": deleted, "session_id": session_id}
