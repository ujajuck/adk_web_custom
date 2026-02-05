"""HTTP client that communicates with the Google ADK api_server."""

from __future__ import annotations

from typing import Any

import httpx

from ..config import settings

_timeout = httpx.Timeout(timeout=120.0, connect=10.0)


async def create_adk_session(
    user_id: str,
    session_id: str,
    state: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """POST /apps/{app}/users/{uid}/sessions/{sid} on the ADK backend."""
    base = settings.ADK_BASE_URL.rstrip("/")
    app = settings.ADK_APP_NAME
    url = f"{base}/apps/{app}/users/{user_id}/sessions/{session_id}"

    async with httpx.AsyncClient(timeout=_timeout) as client:
        resp = await client.post(url, json=state or {})
        resp.raise_for_status()
        return resp.json()


async def send_message_to_adk(
    user_id: str,
    session_id: str,
    message: str,
) -> list[dict[str, Any]]:
    """POST /run on the ADK backend and return the list of events."""
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
        data = resp.json()
        # ADK returns a list of events
        if isinstance(data, list):
            return data
        return [data] if data else []
