# agent/callbacks/before_tool_router.py

import logging
from typing import Any, Dict, Optional

from google.adk.tools.base_tool import BaseTool
from google.adk.tools.tool_context import ToolContext

from ..policies.before_tool_inject_artifact_tabular import (
    before_tool_inject_artifact_tabular,
)

ToolPolicy = callable

BEFORE_TOOL_POLICIES: Dict[str, ToolPolicy] = {
    # MCP import_server(prefix="analytics") 기준
    "ml": before_tool_inject_artifact_tabular,
}


def before_tool_callback_router(
    tool: BaseTool,
    args: Dict[str, Any],
    tool_context: ToolContext,
) -> Optional[Dict[str, Any]]:
    tool_name = getattr(tool, "name", "")
    logging.info(f"==> Called before_tool_callback: {tool_name}")

    # prefix 기준 라우팅 (analytics_xxx)
    prefix = tool_name.split("_", 1)[0] if "_" in tool_name else tool_name
    policy = BEFORE_TOOL_POLICIES.get(prefix)

    if not policy:
        return None

    return policy(tool, args, tool_context)
