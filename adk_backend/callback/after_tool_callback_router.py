# agent/callbacks/after_tool_callback_router.py
"""after_tool_callback: 툴 실행 완료 후 결과를 가공/저장하는 콜백 라우터.

ADK after_tool_callback 시그니처:
    async def after_tool_callback(
        tool: BaseTool,
        args: Dict[str, Any],
        tool_context: ToolContext,
        tool_response: Any,
    ) -> Optional[Dict[str, Any]]

반환값:
- None: 원본 tool_response 사용
- dict: 수정된 응답으로 교체
"""

import logging
from typing import Any, Callable, Dict, Optional

from google.adk.tools.base_tool import BaseTool
from google.adk.tools.tool_context import ToolContext

from ..policies.after_tool_save_outputs import after_tool_save_outputs

log = logging.getLogger(__name__)

# 툴 prefix → 정책 매핑
AfterToolPolicy = Callable[
    [BaseTool, Dict[str, Any], ToolContext, Any],
    Optional[Dict[str, Any]],
]

AFTER_TOOL_POLICIES: Dict[str, AfterToolPolicy] = {
    "analytics": after_tool_save_outputs,
    "ml": after_tool_save_outputs,
}


async def after_tool_callback_router(
    tool: BaseTool,
    args: Dict[str, Any],
    tool_context: ToolContext,
    tool_response: Any,
) -> Optional[Dict[str, Any]]:
    """툴 실행 완료 후 호출. prefix 기준으로 정책을 라우팅한다."""
    tool_name = getattr(tool, "name", "") or tool.__class__.__name__
    log.info("==> Called after_tool_callback: %s", tool_name)

    # prefix 기준 라우팅 (analytics_xxx, ml_xxx 등)
    prefix = tool_name.split("_", 1)[0] if "_" in tool_name else tool_name
    policy = AFTER_TOOL_POLICIES.get(prefix)

    if not policy:
        return None

    # 정책 호출 (async 지원)
    result = policy(tool, args, tool_context, tool_response)
    if hasattr(result, "__await__"):
        result = await result

    return result
