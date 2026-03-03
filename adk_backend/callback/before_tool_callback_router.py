# agent/callbacks/before_tool_router.py

import logging
from typing import Any, Dict, Optional

from google.adk.tools.base_tool import BaseTool
from google.adk.tools.tool_context import ToolContext

from ..policies.before_tool_inject_artifact_tabular import (
    before_tool_inject_artifact_tabular,
)

ToolPolicy = callable

# 아티팩트 주입이 필요한 MCP 툴 목록 (prefix 포함)
ARTIFACT_INJECTION_TOOLS = {
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
    "line_plot", #TODO 변경된 line plot 에서 source_type이 artifact인 데이터를 보낼때 session_id 와 user_id를 추가한 주소를 보내도록 콜백추가
    "pie_chart",
}


async def before_tool_callback_router(
    tool: BaseTool,
    args: Dict[str, Any],
    tool_context: ToolContext,
) -> Optional[Dict[str, Any]]:
    tool_name = getattr(tool, "name", "")
    logging.info(f"==> Called before_tool_callback: {tool_name}")

    # source_type="artifact" 처리가 필요한 툴인지 확인
    source_type = args.get("source_type")

    if tool_name in ARTIFACT_INJECTION_TOOLS:
        # source_type이 "artifact"이거나 artifact_filename이 있으면 아티팩트 주입
        if source_type == "artifact" or args.get("artifact_filename"):
            return await before_tool_inject_artifact_tabular(tool, args, tool_context)

    return None
