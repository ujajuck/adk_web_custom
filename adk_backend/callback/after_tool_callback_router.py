import logging
from typing import Callable, Dict, Optional

from google.genai import types
from google.adk.context import CallbackContext  

from ..policies.after_tool_save_outputs import after_tool_save_outputs
AgentPolicy = Callable[[CallbackContext], Optional[types.Content]]

BEFORE_AGENT_POLICIES: Dict[str, AgentPolicy] = {
    "analytics": after_tool_save_outputs,
    # "plotting": _heartbeat_gatekeeper,
}

def after_tool_callback_router(ctx: CallbackContext) -> Optional[types.Content]:
    agent_name = ctx.agent_name
    logging.info(f"==> Called after_tool_callback: {agent_name}")
    logging.debug(f"==> user_content: {getattr(ctx, 'user_content', None)}")

    policy = BEFORE_AGENT_POLICIES.get(agent_name)
    if not policy:
        return None
    return policy(ctx)
