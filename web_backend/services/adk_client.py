"""HTTP client that communicates with the Google ADK api_server.

ADK 버전별 호환성 처리
─────────────────────
* 세션 생성: 409 Conflict → 이미 존재하는 세션이므로 정상 처리
* /run 응답 형식
  - 신형식: {"status": "success"|"error", "outputs": [...]}
  - 구형식: JSON 배열 [event, event, ...] 또는 NDJSON/SSE
  → 모두 {"status": ..., "outputs": [], "events": [...]} 형태로 정규화해서 반환
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


def _parse_run_response(content_type: str, text: str) -> dict[str, Any]:
    """ADK /run 응답을 파싱한다.

    신형식 (권장):
    {
      "status": "success"|"error",
      "outputs": [{"type": "resource_link", "uri": "...", "mime_type": "..."}]
    }

    구형식 (하위 호환):
    JSON 배열 [event, event, ...] → {"status": "success", "outputs": [], "events": [...]} 로 변환
    """
    stripped = text.strip()

    # ── 1. 신형식 { status, outputs } ─────────────────────────────────────
    if stripped.startswith("{"):
        try:
            result = json.loads(stripped)
            if isinstance(result, dict) and "status" in result:
                return result
        except json.JSONDecodeError:
            pass

    # ── 2. 구형식 JSON 배열 → 신형식으로 변환 ─────────────────────────────
    if stripped.startswith("["):
        try:
            events = json.loads(stripped)
            if isinstance(events, list):
                return {"status": "success", "outputs": [], "events": events}
        except json.JSONDecodeError:
            pass

    # ── 3. NDJSON / SSE 줄별 파싱 (구형식) ────────────────────────────────
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
                # 신형식이 SSE로 왔을 수 있음
                if "status" in obj and "outputs" in obj:
                    return obj
                events.append(obj)
            elif isinstance(obj, list):
                events.extend(obj)
        except json.JSONDecodeError:
            log.debug("Skipping non-JSON line from ADK /run: %.120s", line)

    return {"status": "success", "outputs": [], "events": events}


async def send_message_to_adk(
    user_id: str,
    session_id: str,
    message: str,
) -> dict[str, Any]:
    """POST /run on the ADK backend and return the response dict.

    반환 형식:
    {
      "status": "success"|"error",
      "outputs": [...],      # 신형식
      "events": [...]        # 구형식 (하위 호환)
    }
    """
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
