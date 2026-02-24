# agent/callbacks/router_before_agent.py
from __future__ import annotations

import logging
from typing import Callable, Dict, Optional

from google.genai import types
from google.adk.agents.callback_context import CallbackContext

AgentPolicy = Callable[[CallbackContext], Optional[types.Content]]

def _heartbeat_gatekeeper(ctx: CallbackContext) -> Optional[types.Content]:
    """에이전트 실행 전 헬스체크/차단 정책(예시)."""
    # TODO: 여기서 MCP/LLM 엔드포인트 health check 등을 수행
    ok = True
    if ok:
        return None
    # 차단하고 싶으면 types.Content 반환(콜백 타입별 반환 규칙 문서 참고) :contentReference[oaicite:4]{index=4}
    return types.Content(role="assistant", parts=[types.Part(text="현재 백엔드가 준비되지 않았습니다.")])

BEFORE_AGENT_POLICIES: Dict[str, AgentPolicy] = {
    "analytics": _heartbeat_gatekeeper,
    # "plotting": _heartbeat_gatekeeper,
}

def before_agent_callback_router(ctx: CallbackContext) -> Optional[types.Content]:
    agent_name = ctx.agent_name
    logging.info(f"==> Called before_agent_callback: {agent_name}")
    logging.debug(f"==> user_content: {getattr(ctx, 'user_content', None)}")

    policy = BEFORE_AGENT_POLICIES.get(agent_name)
    if not policy:
        return None
    return policy(ctx)
