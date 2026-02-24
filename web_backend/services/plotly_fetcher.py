"""Fetch Plotly figure JSON from MCP resource URLs."""

from __future__ import annotations

import json
import logging
import re
from typing import Any

import httpx

log = logging.getLogger(__name__)

# MCP 서버 기본 URL
MCP_BASE_URL = "http://127.0.0.1:8001"

# Resource ID 추출 패턴 (mcp://resource/xxx.json에서 xxx 추출)
_RESOURCE_ID_PATTERN = re.compile(r'mcp://resource/([a-f0-9]+)\.json', re.IGNORECASE)


async def fetch_plotly_from_url(url: str) -> dict[str, Any] | None:
    """MCP resource URL에서 Plotly JSON을 가져온다.

    URL 형식:
    - https://adk-resource-host.com/mcp://resource/abc123.json
    - mcp://resource/abc123.json

    Returns: {"title": str, "fig": {...}} or None
    """
    # resource ID 추출
    match = _RESOURCE_ID_PATTERN.search(url)
    if not match:
        log.warning("Could not extract resource ID from URL: %s", url)
        return None

    resource_id = match.group(1)
    log.info("Fetching Plotly resource: %s", resource_id)

    # MCP 서버에서 리소스 가져오기 시도
    # 방법 1: 직접 HTTP GET (fastmcp가 리소스를 HTTP로 노출하는 경우)
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            # MCP HTTP 리소스 엔드포인트 시도
            for endpoint in [
                f"{MCP_BASE_URL}/resources/{resource_id}.json",
                f"{MCP_BASE_URL}/mcp/resources/{resource_id}.json",
                f"{MCP_BASE_URL}/resource/{resource_id}.json",
            ]:
                try:
                    resp = await client.get(endpoint)
                    if resp.status_code == 200:
                        data = resp.json()
                        log.info("Fetched Plotly JSON from %s", endpoint)
                        return _parse_plotly_json(data, resource_id)
                except Exception as e:
                    log.debug("Failed to fetch from %s: %s", endpoint, e)
                    continue

            # 원본 URL 직접 시도 (http/https인 경우)
            if url.startswith("http"):
                # URL에서 mcp:// 부분 제거하고 정규화
                clean_url = url
                resp = await client.get(clean_url)
                if resp.status_code == 200:
                    data = resp.json()
                    return _parse_plotly_json(data, resource_id)

    except Exception as exc:
        log.warning("Failed to fetch Plotly from URL %s: %s", url, exc)

    return None


def _parse_plotly_json(data: Any, resource_id: str) -> dict[str, Any] | None:
    """Plotly JSON 데이터를 파싱하여 표준 형식으로 반환."""
    if not isinstance(data, dict):
        return None

    # Plotly figure 형식 확인
    if "data" in data and isinstance(data["data"], list):
        # 직접 Plotly figure 형식
        layout = data.get("layout", {})
        title = ""
        lt = layout.get("title")
        if isinstance(lt, str):
            title = lt
        elif isinstance(lt, dict):
            title = lt.get("text", "")

        return {
            "title": title or f"Chart {resource_id[:8]}",
            "fig": {
                "data": data["data"],
                "layout": layout,
                "config": data.get("config", {}),
                "frames": data.get("frames") if isinstance(data.get("frames"), list) else None,
            }
        }

    # 다른 형식 (graph 키에 JSON 문자열이 있는 경우)
    if "graph" in data and isinstance(data["graph"], str):
        try:
            fig_obj = json.loads(data["graph"])
            return _parse_plotly_json(fig_obj, resource_id)
        except json.JSONDecodeError:
            pass

    return None
