# agent/callbacks/before_tool_router.py

import logging
from typing import Any, Dict, Optional

from google.adk.tools.base_tool import BaseTool
from google.adk.tools.tool_context import ToolContext

from ..policies.before_tool_inject_artifact_tabular import (
    before_tool_inject_artifact_tabular,
)

ToolPolicy = callable

# 아티팩트 주입이 필요한 MCP 툴 목록
ARTIFACT_INJECTION_TOOLS = {
    # plot_toolbox
    "bar_plot",
    "histogram",
    "scatter_plot",
    "line_plot",
    "pie_chart",
    # preprocess_toolbox
    "fill_missing",
    "normalize",
    "encode_categorical",
    # ml_toolbox
    "linear_regression",
    "random_forest_classifier",
    "kmeans_clustering",
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
