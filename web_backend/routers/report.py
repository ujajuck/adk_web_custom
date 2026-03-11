"""Report generation endpoint - summarizes conversations and artifacts."""

from __future__ import annotations

import json
import logging
from datetime import datetime
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from ..database import get_db
from ..services.flow_store import flow_store
from ..services.csv_store import csv_store
from ..services.plotly_store import plotly_store

router = APIRouter(prefix="/api/report", tags=["report"])
log = logging.getLogger(__name__)


class ReportRequest(BaseModel):
    user_id: str
    session_id: str
    include_artifacts: bool = True
    include_flow: bool = True
    include_chat_history: bool = True


class ArtifactSummary(BaseModel):
    name: str
    type: str
    description: str
    details: Dict[str, Any]


class FlowSummary(BaseModel):
    n_nodes: int
    n_edges: int
    input_artifacts: List[str]
    output_artifacts: List[str]
    tools_used: List[str]


class ChatSummary(BaseModel):
    total_messages: int
    user_messages: int
    assistant_messages: int
    topics: List[str]
    key_actions: List[str]


class ReportResponse(BaseModel):
    session_id: str
    user_id: str
    generated_at: str
    title: str
    summary: str
    artifacts: List[ArtifactSummary]
    flow: Optional[FlowSummary]
    chat: Optional[ChatSummary]
    recommendations: List[str]


@router.post("", response_model=ReportResponse)
async def generate_report(req: ReportRequest):
    """Generate a comprehensive report of the session."""
    log.info("Generating report for user=%s session=%s", req.user_id, req.session_id)

    artifacts: List[ArtifactSummary] = []
    flow_summary: Optional[FlowSummary] = None
    chat_summary: Optional[ChatSummary] = None
    recommendations: List[str] = []

    # Gather artifact summaries
    if req.include_artifacts:
        artifacts = await _gather_artifact_summaries(req.session_id)

    # Gather flow summary
    if req.include_flow:
        flow_summary = _gather_flow_summary(req.session_id)

    # Gather chat history summary
    if req.include_chat_history:
        chat_summary = await _gather_chat_summary(req.user_id, req.session_id)

    # Generate overall summary
    summary = _generate_summary(artifacts, flow_summary, chat_summary)

    # Generate recommendations
    recommendations = _generate_recommendations(artifacts, flow_summary, chat_summary)

    # Generate title
    title = _generate_title(chat_summary, artifacts)

    return ReportResponse(
        session_id=req.session_id,
        user_id=req.user_id,
        generated_at=datetime.now().isoformat(),
        title=title,
        summary=summary,
        artifacts=artifacts,
        flow=flow_summary,
        chat=chat_summary,
        recommendations=recommendations,
    )


@router.get("/{session_id}")
async def get_session_report(session_id: str, user_id: str):
    """Get a quick report for a session."""
    req = ReportRequest(user_id=user_id, session_id=session_id)
    return await generate_report(req)


async def _gather_artifact_summaries(session_id: str) -> List[ArtifactSummary]:
    """Gather summaries of all artifacts in the session."""
    summaries = []

    # CSV artifacts
    for file_id, info in csv_store._store.items():
        if file_id.startswith(session_id):
            df = info.get("df")
            if df is not None:
                summaries.append(ArtifactSummary(
                    name=info.get("filename", file_id),
                    type="csv",
                    description=f"CSV 데이터 ({len(df)}행 x {len(df.columns)}열)",
                    details={
                        "rows": len(df),
                        "columns": len(df.columns),
                        "column_names": list(df.columns)[:10],
                        "numeric_columns": df.select_dtypes(include=['number']).columns.tolist()[:5],
                        "missing_values": int(df.isna().sum().sum()),
                    }
                ))

    # Plotly artifacts
    for fig_id, info in plotly_store._store.items():
        if fig_id.startswith(session_id):
            fig = info.get("fig", {})
            fig_type = _detect_plot_type(fig)
            summaries.append(ArtifactSummary(
                name=info.get("title", fig_id),
                type="plotly",
                description=f"Plotly 시각화 ({fig_type})",
                details={
                    "plot_type": fig_type,
                    "n_traces": len(fig.get("data", [])),
                }
            ))

    return summaries


def _detect_plot_type(fig: Dict[str, Any]) -> str:
    """Detect the type of Plotly figure."""
    data = fig.get("data", [])
    if not data:
        return "unknown"

    first_trace = data[0]
    trace_type = first_trace.get("type", "scatter")

    type_names = {
        "scatter": "산점도",
        "bar": "막대그래프",
        "histogram": "히스토그램",
        "heatmap": "히트맵",
        "pie": "파이차트",
        "box": "박스플롯",
        "line": "선그래프",
    }

    return type_names.get(trace_type, trace_type)


def _gather_flow_summary(session_id: str) -> Optional[FlowSummary]:
    """Gather flow graph summary."""
    flow_data = flow_store.get(session_id)
    if not flow_data:
        return None

    nodes = flow_data.nodes
    edges = flow_data.edges

    input_artifacts = [n.label for n in nodes if n.node_type == "input"]
    output_artifacts = [n.label for n in nodes if n.node_type == "output"]
    tools_used = list(set(e.tool_name for e in edges if e.tool_name))

    return FlowSummary(
        n_nodes=len(nodes),
        n_edges=len(edges),
        input_artifacts=input_artifacts,
        output_artifacts=output_artifacts,
        tools_used=tools_used,
    )


async def _gather_chat_summary(user_id: str, session_id: str) -> Optional[ChatSummary]:
    """Gather chat history summary."""
    db = await get_db()
    try:
        cursor = await db.execute(
            """SELECT request_message, response_text FROM chat_jobs
               WHERE user_id = ? AND session_id = ?
               ORDER BY created_at ASC""",
            (user_id, session_id)
        )
        rows = await cursor.fetchall()
    finally:
        await db.close()

    if not rows:
        return None

    user_messages = [r[0] for r in rows if r[0]]
    assistant_messages = [r[1] for r in rows if r[1]]

    # Extract topics and key actions
    topics = _extract_topics(user_messages + assistant_messages)
    key_actions = _extract_key_actions(assistant_messages)

    return ChatSummary(
        total_messages=len(rows) * 2,
        user_messages=len(user_messages),
        assistant_messages=len(assistant_messages),
        topics=topics[:5],
        key_actions=key_actions[:5],
    )


def _extract_topics(messages: List[str]) -> List[str]:
    """Extract main topics from messages."""
    topics = set()

    keywords = {
        "데이터 분석": ["분석", "통계", "데이터"],
        "시각화": ["그래프", "차트", "시각화", "plot", "figure"],
        "전처리": ["전처리", "결측", "이상치", "정규화"],
        "모델링": ["모델", "예측", "분류", "회귀", "클러스터링"],
        "파일 처리": ["파일", "csv", "엑셀", "로드", "저장"],
    }

    combined = " ".join(messages).lower()

    for topic, kws in keywords.items():
        if any(kw in combined for kw in kws):
            topics.add(topic)

    return list(topics)


def _extract_key_actions(messages: List[str]) -> List[str]:
    """Extract key actions performed."""
    actions = []

    action_patterns = [
        ("데이터 로드", ["로드", "불러", "읽"]),
        ("그래프 생성", ["그래프", "차트", "시각화"]),
        ("결측치 처리", ["결측", "missing", "null"]),
        ("이상치 제거", ["이상치", "outlier"]),
        ("모델 학습", ["학습", "train", "fit"]),
        ("예측 수행", ["예측", "predict"]),
    ]

    combined = " ".join(messages).lower()

    for action, patterns in action_patterns:
        if any(p in combined for p in patterns):
            actions.append(action)

    return actions


def _generate_summary(
    artifacts: List[ArtifactSummary],
    flow: Optional[FlowSummary],
    chat: Optional[ChatSummary]
) -> str:
    """Generate overall session summary."""
    parts = []

    if chat:
        parts.append(f"이 세션에서 {chat.total_messages}개의 메시지가 교환되었습니다.")
        if chat.topics:
            parts.append(f"주요 주제: {', '.join(chat.topics)}")

    if artifacts:
        csv_count = sum(1 for a in artifacts if a.type == "csv")
        plot_count = sum(1 for a in artifacts if a.type == "plotly")
        if csv_count > 0:
            parts.append(f"{csv_count}개의 데이터셋이 처리되었습니다.")
        if plot_count > 0:
            parts.append(f"{plot_count}개의 시각화가 생성되었습니다.")

    if flow:
        parts.append(f"데이터 흐름: {flow.n_nodes}개 노드, {flow.n_edges}개 엣지")
        if flow.tools_used:
            parts.append(f"사용된 도구: {', '.join(flow.tools_used[:3])}")

    if not parts:
        return "세션에서 수행된 작업이 없습니다."

    return " ".join(parts)


def _generate_recommendations(
    artifacts: List[ArtifactSummary],
    flow: Optional[FlowSummary],
    chat: Optional[ChatSummary]
) -> List[str]:
    """Generate recommendations based on session analysis."""
    recommendations = []

    # Check for missing data
    for artifact in artifacts:
        if artifact.type == "csv":
            missing = artifact.details.get("missing_values", 0)
            if missing > 0:
                recommendations.append(
                    f"'{artifact.name}'에 {missing}개의 결측치가 있습니다. "
                    "fill_missing 도구로 처리를 권장합니다."
                )

    # Check for many columns
    for artifact in artifacts:
        if artifact.type == "csv":
            cols = artifact.details.get("columns", 0)
            if cols > 20:
                recommendations.append(
                    f"'{artifact.name}'에 {cols}개의 컬럼이 있습니다. "
                    "PCA를 통한 차원 축소를 고려해보세요."
                )

    # Suggest visualization
    csv_artifacts = [a for a in artifacts if a.type == "csv"]
    plot_artifacts = [a for a in artifacts if a.type == "plotly"]

    if csv_artifacts and not plot_artifacts:
        recommendations.append(
            "데이터셋이 있지만 시각화가 없습니다. "
            "데이터 이해를 위해 히스토그램이나 박스플롯을 생성해보세요."
        )

    # Suggest next steps
    if flow and len(flow.output_artifacts) > 0:
        recommendations.append(
            "분석 결과를 노트북에 저장하여 나중에 다시 확인할 수 있습니다."
        )

    return recommendations[:5]


def _generate_title(chat: Optional[ChatSummary], artifacts: List[ArtifactSummary]) -> str:
    """Generate a title for the report."""
    if chat and chat.topics:
        return f"{chat.topics[0]} 분석 리포트"

    if artifacts:
        first_artifact = artifacts[0]
        return f"'{first_artifact.name}' 분석 리포트"

    return "세션 리포트"
