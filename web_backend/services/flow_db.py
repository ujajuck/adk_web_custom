"""Flow DB service – persist and restore flow edges from SQLite."""

from __future__ import annotations

import json
import logging
from typing import Any

import aiosqlite

from ..config import settings

log = logging.getLogger(__name__)


async def save_flow_edges(
    session_id: str,
    new_edges: list,  # list[FlowEdge]
    all_nodes: list,  # list[FlowNode]
) -> None:
    """새 엣지들을 flow_edges 테이블에 저장 (중복 무시)."""
    if not new_edges:
        return

    # node_id → artifact_name 맵 구성
    node_art: dict[str, str | None] = {}
    for n in all_nodes:
        node_art[n.id] = getattr(n, "artifact_name", None) or getattr(n, "label", None)

    rows = []
    for edge in new_edges:
        input_art = node_art.get(edge.source)
        output_art = node_art.get(edge.target)
        rows.append((
            session_id,
            edge.id,
            edge.agent_name or "",
            edge.tool_name or "",
            input_art,
            output_art,
            json.dumps(edge.tool_args or {}, ensure_ascii=False),
        ))

    async with aiosqlite.connect(settings.DB_PATH) as db:
        await db.executemany(
            """INSERT OR IGNORE INTO flow_edges
               (session_id, edge_id, agent_name, tool_name,
                input_artifact, output_artifact, tool_args_json)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            rows,
        )
        await db.commit()
    log.debug("Saved %d flow edges for session %s", len(rows), session_id)


async def get_flow_data(session_id: str) -> dict[str, Any]:
    """DB에서 세션 플로우를 읽어 FlowData dict 반환."""
    async with aiosqlite.connect(settings.DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute(
            "SELECT * FROM flow_edges WHERE session_id = ? ORDER BY id",
            (session_id,),
        )
        rows = await cursor.fetchall()

    return build_flow_data(session_id, rows)


def build_flow_data(session_id: str, rows: list) -> dict[str, Any]:
    """DB row 목록 → FlowData dict 변환.

    결과 구조:
    {
      "session_id": ...,
      "nodes": [{"id", "label", "artifact_name", "node_type"}, ...],
      "edges": [{"id", "source", "target", "tool_name", "agent_name", "label"}, ...]
    }
    """
    if not rows:
        return {"session_id": session_id, "nodes": [], "edges": []}

    nodes_map: dict[str, dict] = {}
    edges: list[dict] = []

    for row in rows:
        in_art = row["input_artifact"]
        out_art = row["output_artifact"]

        if in_art and in_art not in nodes_map:
            nodes_map[in_art] = {
                "id": f"node_{in_art}",
                "label": in_art,
                "node_type": "input",
                "artifact_name": in_art,
            }

        if out_art and out_art not in nodes_map:
            nodes_map[out_art] = {
                "id": f"node_{out_art}",
                "label": out_art,
                "node_type": "output",
                "artifact_name": out_art,
            }

        src_id = f"node_{in_art}" if in_art else "node_start"
        tgt_id = f"node_{out_art}" if out_art else f"node_{row['edge_id']}_result"

        if src_id == "node_start" and "node_start" not in nodes_map:
            nodes_map["node_start"] = {
                "id": "node_start",
                "label": "시작",
                "node_type": "input",
                "artifact_name": None,
            }

        if tgt_id not in nodes_map and not out_art:
            # 아티팩트 없는 툴의 가상 출력 노드
            nodes_map[tgt_id] = {
                "id": tgt_id,
                "label": row["tool_name"] or "결과",
                "node_type": "output",
                "artifact_name": None,
            }

        edges.append({
            "id": row["edge_id"],
            "source": src_id,
            "target": tgt_id,
            "tool_name": row["tool_name"],
            "agent_name": row["agent_name"] or "",
            "label": row["tool_name"],
        })

    return {
        "session_id": session_id,
        "nodes": list(nodes_map.values()),
        "edges": edges,
    }
