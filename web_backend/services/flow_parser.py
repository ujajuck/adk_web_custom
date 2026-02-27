"""Flow parser – extracts tool usage and artifact flow from ADK events.

ADK 이벤트에서 툴 호출 정보를 파싱하여 아티팩트 흐름 그래프를 구성한다.
각 노드는 아티팩트(입력/출력 데이터)이고, 엣지는 툴 호출을 나타낸다.
"""

from __future__ import annotations

import os
import re
import logging
from typing import Any, Optional
from dataclasses import dataclass, field, asdict

log = logging.getLogger(__name__)


@dataclass
class FlowNode:
    """아티팩트 노드."""
    id: str
    label: str
    node_type: str  # "input" | "output" | "intermediate"
    artifact_name: Optional[str] = None
    file_name: Optional[str] = None
    created_at: Optional[str] = None

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class FlowEdge:
    """툴 호출 엣지."""
    id: str
    source: str  # source node id
    target: str  # target node id
    tool_name: str
    tool_args: dict = field(default_factory=dict)
    label: Optional[str] = None

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class ArtifactFlow:
    """세션의 전체 아티팩트 흐름."""
    session_id: str
    nodes: list[FlowNode] = field(default_factory=list)
    edges: list[FlowEdge] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "session_id": self.session_id,
            "nodes": [n.to_dict() for n in self.nodes],
            "edges": [e.to_dict() for e in self.edges],
        }

    def add_node(self, node: FlowNode) -> None:
        # 중복 방지
        if not any(n.id == node.id for n in self.nodes):
            self.nodes.append(node)

    def add_edge(self, edge: FlowEdge) -> None:
        if not any(e.id == edge.id for e in self.edges):
            self.edges.append(edge)


def _extract_tool_calls(events: list[dict]) -> list[dict]:
    """ADK 이벤트에서 툴 호출 정보 추출.

    ADK 이벤트 구조:
    - content.parts[].functionCall: 툴 호출 요청
    - content.parts[].functionResponse: 툴 호출 응답
    """
    tool_calls = []

    for ev in events:
        content = ev.get("content") or {}
        parts = content.get("parts") or []

        for part in parts:
            # 툴 호출 요청
            func_call = part.get("functionCall")
            if func_call:
                tool_calls.append({
                    "type": "call",
                    "name": func_call.get("name", "unknown"),
                    "args": func_call.get("args", {}),
                })

            # 툴 호출 응답
            func_resp = part.get("functionResponse")
            if func_resp:
                tool_calls.append({
                    "type": "response",
                    "name": func_resp.get("name", "unknown"),
                    "response": func_resp.get("response", {}),
                })

    return tool_calls


def _extract_artifact_locator(args: dict) -> Optional[dict]:
    """툴 인자에서 입력 아티팩트 정보 추출.

    지원 형식:
    1. source_type: "artifact" (신규 multi-input 방식)
    2. artifact_locator dict (기존 방식)
    3. kind: "locator" + artifact_locator (기존 방식)
    """
    # 1. 신규 source_type: "artifact" 형식
    if args.get("source_type") == "artifact":
        artifact_name = args.get("artifact_name")
        if artifact_name:
            return {
                "artifact_name": artifact_name,
                "file_name": artifact_name,
                "columns": args.get("columns"),
            }

    # 2. artifact_locator 패턴 (기존)
    locator = args.get("artifact_locator")
    if isinstance(locator, dict):
        return {
            "artifact_name": locator.get("artifact_name"),
            "file_name": locator.get("file_name"),
        }

    # 3. kind가 locator인 경우 (기존)
    if args.get("kind") == "locator" and "artifact_locator" in args:
        loc = args["artifact_locator"]
        if isinstance(loc, dict):
            return {
                "artifact_name": loc.get("artifact_name"),
                "file_name": loc.get("file_name"),
            }

    return None


def _extract_output_artifact(response: dict) -> Optional[dict]:
    """툴 응답에서 출력 아티팩트 정보 추출.

    지원 형식:
    1. ADK 툴 응답: {"ok": true, "filename": "...", "version": ...}
    2. MCP 툴 응답: {"outputs": [{"type": "resource_link", "uri": "..."}]}
    3. description에서 파일명 추출
    """
    # 1. ADK 툴 응답 형식 (load_csv_from_path_and_save_artifact 등)
    if response.get("ok") and response.get("filename"):
        filename = response["filename"]
        version = response.get("version")
        return {
            "artifact_name": filename,
            "file_name": filename,
            "version": version,
        }

    # 2. outputs에서 resource_link 찾기 (MCP 툴)
    outputs = response.get("outputs") or []
    for out in outputs:
        if isinstance(out, dict):
            if out.get("type") == "resource_link":
                uri = out.get("uri", "")
                # mcp://resource/xxx.json 패턴에서 파일명 추출
                match = re.search(r'mcp://resource/([^/\s]+)', uri)
                if match:
                    return {
                        "artifact_name": match.group(1),
                        "file_name": match.group(1),
                        "uri": uri,
                    }

    # 3. description에서 정보 추출 시도
    desc = response.get("description", "")
    if desc:
        # 파일명 패턴 찾기
        match = re.search(r'(\w+\.(csv|json|png|jpg|html))', desc, re.IGNORECASE)
        if match:
            return {
                "artifact_name": match.group(1),
                "file_name": match.group(1),
            }

    return None


def parse_artifact_flow(
    session_id: str,
    events: list[dict],
    artifact_delta: dict[str, int],
    existing_flow: Optional[ArtifactFlow] = None,
) -> ArtifactFlow:
    """ADK 이벤트에서 아티팩트 흐름 그래프 파싱.

    Args:
        session_id: 세션 ID
        events: ADK 이벤트 목록
        artifact_delta: {filename: version} 형태의 아티팩트 변경 정보
        existing_flow: 기존 플로우 (누적용)

    Returns:
        ArtifactFlow: 파싱된 아티팩트 흐름
    """
    flow = existing_flow or ArtifactFlow(session_id=session_id)

    tool_calls = _extract_tool_calls(events)

    # 툴 호출 쌍 매칭 (call → response)
    pending_calls: list[dict] = []

    for tc in tool_calls:
        if tc["type"] == "call":
            pending_calls.append(tc)
        elif tc["type"] == "response" and pending_calls:
            # 가장 최근 call과 매칭
            call = pending_calls.pop(0)

            tool_name = call.get("name", "unknown")
            tool_args = call.get("args", {})
            response = tc.get("response", {})

            # 입력 아티팩트 추출
            input_artifact = _extract_artifact_locator(tool_args)

            # 출력 아티팩트 추출
            output_artifact = _extract_output_artifact(response)

            # 노드 및 엣지 생성
            if input_artifact or output_artifact:
                edge_id = f"edge_{len(flow.edges)}_{tool_name}"

                # 입력 노드
                if input_artifact:
                    input_id = f"node_{input_artifact.get('artifact_name', 'input')}"
                    input_node = FlowNode(
                        id=input_id,
                        label=input_artifact.get("file_name", "입력 데이터"),
                        node_type="input",
                        artifact_name=input_artifact.get("artifact_name"),
                        file_name=input_artifact.get("file_name"),
                    )
                    flow.add_node(input_node)
                else:
                    input_id = None

                # 출력 노드
                if output_artifact:
                    output_id = f"node_{output_artifact.get('artifact_name', 'output')}"
                    output_node = FlowNode(
                        id=output_id,
                        label=output_artifact.get("file_name", "출력 결과"),
                        node_type="output",
                        artifact_name=output_artifact.get("artifact_name"),
                        file_name=output_artifact.get("file_name"),
                    )
                    flow.add_node(output_node)
                else:
                    output_id = None

                # 엣지 생성 (입력 → 출력)
                if input_id and output_id:
                    edge = FlowEdge(
                        id=edge_id,
                        source=input_id,
                        target=output_id,
                        tool_name=tool_name,
                        tool_args=tool_args,
                        label=_get_tool_label(tool_name, tool_args),
                    )
                    flow.add_edge(edge)
                elif output_id:
                    # 입력 없이 출력만 있는 경우 (데이터 로드 등)
                    # 가상의 시작 노드 생성
                    start_id = "node_start"
                    start_node = FlowNode(
                        id=start_id,
                        label="시작",
                        node_type="input",
                    )
                    flow.add_node(start_node)

                    edge = FlowEdge(
                        id=edge_id,
                        source=start_id,
                        target=output_id,
                        tool_name=tool_name,
                        tool_args=tool_args,
                        label=_get_tool_label(tool_name, tool_args),
                    )
                    flow.add_edge(edge)

    # artifact_delta에서 추가 노드 생성
    for filename, version in artifact_delta.items():
        node_id = f"node_artifact_{filename}_v{version}"
        if not any(n.id == node_id for n in flow.nodes):
            node = FlowNode(
                id=node_id,
                label=f"{filename} (v{version})",
                node_type="output",
                artifact_name=filename,
                file_name=filename,
            )
            flow.add_node(node)

    return flow


def _get_tool_label(tool_name: str, tool_args: Optional[dict] = None) -> str:
    """툴 이름을 사람이 읽기 쉬운 라벨로 변환.

    Args:
        tool_name: 툴 이름
        tool_args: 툴 인자 (컬럼 정보 등 추가 컨텍스트용)
    """
    labels = {
        "bar_plot": "막대 그래프",
        "histogram": "히스토그램",
        "scatter_plot": "산점도",
        "line_plot": "선 그래프",
        "pie_chart": "파이 차트",
        "fill_missing": "결측치 처리",
        "normalize": "정규화",
        "encode_categorical": "범주형 인코딩",
        "linear_regression": "선형 회귀",
        "random_forest_classifier": "랜덤 포레스트",
        "kmeans_clustering": "K-평균 클러스터링",
        "load_csv_from_path_and_save_artifact": "데이터 로드",
    }
    base_label = labels.get(tool_name, tool_name)

    # 컬럼 정보가 있으면 라벨에 추가
    if tool_args:
        # 데이터 로드 툴: 파일 경로 표시
        if tool_name == "load_csv_from_path_and_save_artifact":
            path = tool_args.get("path", "")
            if path:
                # 경로에서 파일명만 추출
                filename = os.path.basename(path)
                return f"{base_label}[{filename}]"
            artifact_name = tool_args.get("artifact_name")
            if artifact_name:
                return f"{base_label}[{artifact_name}]"

        columns = tool_args.get("columns") or tool_args.get("column")
        if columns:
            if isinstance(columns, list):
                col_str = ", ".join(str(c) for c in columns[:3])
                if len(columns) > 3:
                    col_str += "..."
            else:
                col_str = str(columns)
            return f"{base_label}[{col_str}]"

        # x, y 컬럼 정보
        x_col = tool_args.get("x")
        y_col = tool_args.get("y")
        if x_col and y_col:
            return f"{base_label}[{x_col}, {y_col}]"
        elif x_col:
            return f"{base_label}[{x_col}]"

    return base_label
