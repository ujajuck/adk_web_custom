"""Fetch Plotly figure JSON from MCP resource files.

mcp://resource/{job_id}.json URI에서 job_id를 추출해
MCP_RESOURCE_ROOT/{job_id}.json 파일을 직접 읽는다.
"""

from __future__ import annotations

import json
import logging
import re
from pathlib import Path
from typing import Any

from ..config import settings

log = logging.getLogger(__name__)

# mcp://resource/{filename} 에서 파일명 추출
_FILENAME_PATTERN = re.compile(r'mcp://resource/([^)\s"\']+)', re.IGNORECASE)


async def fetch_plotly_from_url(url: str) -> dict[str, Any] | None:
    """mcp://resource/xxx.json URI에서 Plotly figure를 파일로 직접 읽어 반환.

    Returns: {"title": str, "fig": {data, layout, config}} or None
    """
    match = _FILENAME_PATTERN.search(url)
    if not match:
        log.warning("mcp://resource/ 패턴을 찾을 수 없음: %s", url)
        return None

    filename = match.group(1)  # e.g. "bf6ffd572a30416f8b86b2d43edf340f.json"

    root = settings.MCP_RESOURCE_ROOT
    if not root:
        log.warning("MCP_RESOURCE_ROOT가 설정되지 않았습니다. web_backend/.env를 확인하세요.")
        return None

    file_path = Path(root) / filename
    log.info("Reading MCP resource: %s", file_path)

    if not file_path.exists():
        log.warning("MCP resource 파일이 없습니다: %s", file_path)
        return None

    try:
        data = json.loads(file_path.read_text(encoding="utf-8"))
    except Exception as exc:
        log.warning("MCP resource JSON 읽기 실패: %s – %s", file_path, exc)
        return None

    return _parse_plotly_json(data, filename)


def _parse_plotly_json(data: Any, filename: str) -> dict[str, Any] | None:
    """저장된 JSON을 Plotly figure 형식으로 파싱."""
    if not isinstance(data, dict):
        return None

    # bar_plot 저장 형식: {"type":"plotly","title":"...","fig":{...},"meta":{...}}
    if data.get("type") == "plotly" and "fig" in data:
        fig = data["fig"]
        if not isinstance(fig, dict) or not isinstance(fig.get("data"), list):
            return None

        layout = fig.get("layout") or {}
        title = data.get("title") or _title_from_layout(layout) or filename

        return {
            "title": title,
            "fig": {
                "data": fig["data"],
                "layout": layout,
                "config": fig.get("config") or {},
                "frames": fig.get("frames") if isinstance(fig.get("frames"), list) else None,
            },
        }

    # 직접 Plotly figure 형식: {"data":[...],"layout":{...}}
    if "data" in data and isinstance(data["data"], list):
        layout = data.get("layout") or {}
        title = _title_from_layout(layout) or filename
        return {
            "title": title,
            "fig": {
                "data": data["data"],
                "layout": layout,
                "config": data.get("config") or {},
                "frames": data.get("frames") if isinstance(data.get("frames"), list) else None,
            },
        }

    return None


def _title_from_layout(layout: dict) -> str:
    lt = layout.get("title")
    if isinstance(lt, str):
        return lt
    if isinstance(lt, dict):
        return lt.get("text", "")
    return ""
