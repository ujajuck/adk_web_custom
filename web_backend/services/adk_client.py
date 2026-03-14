"""HTTP client for Google ADK api_server."""

from __future__ import annotations

import json
import logging
from typing import Any

import httpx

from ..config import settings

log = logging.getLogger(__name__)

_timeout = httpx.Timeout(timeout=120.0, connect=10.0)


async def create_adk_session(
    user_id: str,
    session_id: str,
    state: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Create ADK session. 409 means session exists, treated as success."""
    base = settings.ADK_BASE_URL.rstrip("/")
    app = settings.ADK_APP_NAME
    url = f"{base}/apps/{app}/users/{user_id}/sessions/{session_id}"

    async with httpx.AsyncClient(timeout=_timeout) as client:
        resp = await client.post(url, json=state or {})

        if resp.status_code == 409:
            log.info("ADK session already exists (409), reusing: %s", session_id)
            return {"session_id": session_id, "user_id": user_id}

        resp.raise_for_status()
        body = resp.json() if resp.content else {}
        if not body:
            body = {"session_id": session_id, "user_id": user_id}
        return body


def _parse_run_response(content_type: str, text: str) -> dict[str, Any]:
    """Parse ADK /run response into {status, outputs, events}."""
    stripped = text.strip()

    # New format: {"status": "...", "outputs": [...]}
    if stripped.startswith("{"):
        try:
            result = json.loads(stripped)
            if isinstance(result, dict) and "status" in result:
                return result
        except json.JSONDecodeError:
            pass

    # Legacy: JSON array -> convert to new format
    if stripped.startswith("["):
        try:
            events = json.loads(stripped)
            if isinstance(events, list):
                return {"status": "success", "outputs": [], "events": events}
        except json.JSONDecodeError:
            pass

    # Legacy: NDJSON/SSE line-by-line
    events: list[dict[str, Any]] = []
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line or line == "[DONE]":
            continue
        if line.startswith("data:"):
            line = line[5:].strip()
        if not line or line == "[DONE]":
            continue
        try:
            obj = json.loads(line)
            if isinstance(obj, dict):
                if "status" in obj and "outputs" in obj:
                    return obj
                events.append(obj)
            elif isinstance(obj, list):
                events.extend(obj)
        except json.JSONDecodeError:
            log.debug("Skipping non-JSON line: %.120s", line)

    return {"status": "success", "outputs": [], "events": events}


def _collect_agent_names(agent_def: Any, names: list[str]) -> None:
    """Recursively collect agent names from ADK app definition."""
    if not isinstance(agent_def, dict):
        return
    name = agent_def.get("name")
    if name:
        names.append(name)
    for sub in agent_def.get("sub_agents") or []:
        _collect_agent_names(sub, names)


async def list_agents() -> list[str]:
    """List available agents from ADK app (falls back to root_agent)."""
    base = settings.ADK_BASE_URL.rstrip("/")
    app = settings.ADK_APP_NAME
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            resp = await client.get(f"{base}/apps/{app}")
            if resp.status_code == 200:
                data = resp.json()
                if isinstance(data, dict):
                    names: list[str] = []
                    _collect_agent_names(data.get("agent") or data, names)
                    if names:
                        return names
    except Exception as e:
        log.debug("Failed to list ADK agents: %s", e)
    return ["root_agent"]


async def send_message_to_adk(
    user_id: str,
    session_id: str,
    message: str,
) -> dict[str, Any]:
    """Send message to ADK. Returns {status, outputs, events}."""
    base = settings.ADK_BASE_URL.rstrip("/")
    app = settings.ADK_APP_NAME

    payload = {
        "appName": app,
        "userId": user_id,
        "sessionId": session_id,
        "newMessage": {"role": "user", "parts": [{"text": message}]},
    }

    async with httpx.AsyncClient(timeout=_timeout) as client:
        resp = await client.post(f"{base}/run", json=payload)
        resp.raise_for_status()

        content_type = resp.headers.get("content-type", "")
        return _parse_run_response(content_type, resp.text)
