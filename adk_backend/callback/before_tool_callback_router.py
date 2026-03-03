# agent/callbacks/before_tool_router.py

import logging
from typing import Any, Dict, Optional

from google.adk.tools.base_tool import BaseTool
from google.adk.tools.tool_context import ToolContext

ToolPolicy = callable

# 아티팩트 소스 정보 주입이 필요한 MCP 툴 목록 (prefix 포함)
ARTIFACT_SOURCE_TOOLS = {
    # plot_toolbox (prefix="plot")
    "plot_bar_plot",
    "plot_histogram",
    "plot_scatter_plot",
    "plot_line_plot",
    "plot_pie_chart",
    # preprocess_toolbox (prefix="preprocess" 또는 없음)
    "preprocess_fill_missing",
    "preprocess_normalize",
    "preprocess_encode_categorical",
    "fill_missing",
    "normalize",
    "encode_categorical",
    # ml_toolbox (prefix="ml" 또는 없음)
    "ml_linear_regression",
    "ml_random_forest_classifier",
    "ml_kmeans_clustering",
    "linear_regression",
    "random_forest_classifier",
    "kmeans_clustering",
    # prefix 없는 버전도 포함 (호환성)
    "bar_plot",
    "histogram",
    "scatter_plot",
    "line_plot",
    "pie_chart",
}


async def before_tool_callback_router(
    tool: BaseTool,
    args: Dict[str, Any],
    tool_context: ToolContext,
) -> Optional[Dict[str, Any]]:
    """MCP 툴 호출 전 args를 가공하는 라우터.

    source.source_type="artifact"일 때 user_id, session_id를 자동 주입하여
    MCP 서버가 아티팩트 파일을 직접 읽을 수 있도록 합니다.
    """
    tool_name = getattr(tool, "name", "")
    logging.info(f"==> Called before_tool_callback: {tool_name}")

    if tool_name not in ARTIFACT_SOURCE_TOOLS:
        return None

    # source 객체 또는 source_type 확인
    source = args.get("source")

    if isinstance(source, dict) and source.get("source_type") == "artifact":
        # Request 스키마 방식: source.source_type = "artifact"
        return _inject_artifact_context_nested(args, tool_context)

    # 레거시 방식: 최상위 source_type
    source_type = args.get("source_type")
    if source_type == "artifact":
        return _inject_artifact_context_flat(args, tool_context)

    return None


def _inject_artifact_context_nested(
    args: Dict[str, Any],
    tool_context: ToolContext,
) -> Dict[str, Any]:
    """source.source_type='artifact'일 때 source에 user_id, session_id 주입.

    Request 스키마 방식에서 사용.
    """
    new_args = dict(args)
    source = dict(new_args["source"])

    # tool_context에서 user_id, session_id 추출
    user_id = getattr(tool_context, "user_id", None)
    session_id = getattr(tool_context, "session_id", None)

    if user_id:
        source["user_id"] = user_id
    if session_id:
        source["session_id"] = session_id

    # 버전 기본값
    if "version" not in source:
        source["version"] = 0

    new_args["source"] = source

    logging.info(
        f"==> Injected artifact context (nested): user_id={user_id}, "
        f"session_id={session_id}, artifact_name={source.get('artifact_name')}"
    )

    return new_args


def _inject_artifact_context_flat(
    args: Dict[str, Any],
    tool_context: ToolContext,
) -> Dict[str, Any]:
    """최상위 source_type='artifact'일 때 user_id, session_id 주입.

    레거시 방식에서 사용.
    """
    new_args = dict(args)

    # tool_context에서 user_id, session_id 추출
    user_id = getattr(tool_context, "user_id", None)
    session_id = getattr(tool_context, "session_id", None)

    if user_id:
        new_args["user_id"] = user_id
    if session_id:
        new_args["session_id"] = session_id

    # 버전 기본값
    if "version" not in new_args:
        new_args["version"] = 0

    logging.info(
        f"==> Injected artifact context (flat): user_id={user_id}, "
        f"session_id={session_id}, artifact_name={args.get('artifact_name')}"
    )

    return new_args
