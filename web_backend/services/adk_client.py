"""HTTP client that communicates with the Google ADK api_server.

ADK 버전별 호환성 처리
─────────────────────
* 세션 생성: 409 Conflict → 이미 존재하는 세션이므로 정상 처리
* /run 응답 형식
  - 구버전 ADK: JSON 배열  [event, event, ...]
  - 신버전 ADK: NDJSON 스트림 / SSE (data: {json}\\n\\n)
  두 형식 모두 파싱해서 list[dict] 로 반환한다.
"""

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
    """POST /apps/{app}/users/{uid}/sessions/{sid} on the ADK backend.

    409 Conflict は「セッションが既に存在する」ことを意味するため、
    エラーとして扱わず既存セッションを再利用する。
    """
    base = settings.ADK_BASE_URL.rstrip("/")
    app = settings.ADK_APP_NAME
    url = f"{base}/apps/{app}/users/{user_id}/sessions/{session_id}"

    async with httpx.AsyncClient(timeout=_timeout) as client:
        resp = await client.post(url, json=state or {})

        if resp.status_code == 409:
            # Session already exists – reuse it
            log.info("ADK session already exists (409), reusing: %s", session_id)
            return {"session_id": session_id, "user_id": user_id}

        resp.raise_for_status()
        body = resp.json() if resp.content else {}
        # Normalise: some ADK versions return {} on success
        if not body:
            body = {"session_id": session_id, "user_id": user_id}
        return body


def _parse_run_response(content_type: str, text: str) -> list[dict[str, Any]]:
    """ADK /run 응답을 list[dict] 로 파싱한다.

    지원 형식:
    1. JSON 배열  – 구버전 ADK (content-type: application/json)
    2. NDJSON     – 신버전 ADK (content-type: application/x-ndjson)
    3. SSE        – 신버전 ADK (content-type: text/event-stream)
       각 줄이 "data: {json}" 형식
    """
    stripped = text.strip()

    # ── 1. JSON 배열 ──────────────────────────────────────────────────────
    if stripped.startswith("["):
        try:
            result = json.loads(stripped)
            if isinstance(result, list):
                return result
        except json.JSONDecodeError:
            pass

    # ── 2. NDJSON / SSE 줄별 파싱 ─────────────────────────────────────────
    events: list[dict[str, Any]] = []
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line or line == "[DONE]":
            continue
        # SSE "data: " 접두사 제거
        if line.startswith("data:"):
            line = line[5:].strip()
        if not line or line == "[DONE]":
            continue
        try:
            obj = json.loads(line)
            if isinstance(obj, dict):
                events.append(obj)
            elif isinstance(obj, list):
                events.extend(obj)
        except json.JSONDecodeError:
            log.debug("Skipping non-JSON line from ADK /run: %.120s", line)

    return events


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

        content_type = resp.headers.get("content-type", "")
        return _parse_run_response(content_type, resp.text)
