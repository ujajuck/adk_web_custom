"""Parse ADK event lists – Python equivalents of the TypeScript parsers in
components/chat/ (extractArtifactDelta, plotlyParsers, adkParsers)."""

from __future__ import annotations

import json
import re
from typing import Any


# ── artifact delta ─────────────────────────────────────────


def extract_artifact_delta(events: Any) -> dict[str, int]:
    """Return {filename: version} from ADK artifact deltas."""
    if not isinstance(events, list):
        return {}
    result: dict[str, int] = {}
    for ev in events:
        delta = (ev.get("actions") or {}).get("artifactDelta")
        if not isinstance(delta, dict):
            continue
        for k, v in delta.items():
            try:
                result[str(k)] = int(v)
            except (ValueError, TypeError):
                pass
    return result


# ── plotly figure ──────────────────────────────────────────


def extract_plotly_fig(events: Any) -> dict[str, Any] | None:
    """DFS through events to find outputs[0].graph (a Plotly JSON string).
    Returns {"title": str, "fig": {data, layout, config, frames}} or None."""
    if not isinstance(events, list):
        return None

    visited: set[int] = set()

    def _find_graph(node: Any) -> dict[str, str] | None:
        if node is None or not isinstance(node, (dict, list)):
            return None
        nid = id(node)
        if nid in visited:
            return None
        visited.add(nid)

        if isinstance(node, dict):
            outputs = node.get("outputs")
            if isinstance(outputs, list) and len(outputs) > 0:
                graph = (outputs[0] or {}).get("graph") if isinstance(outputs[0], dict) else None
                if isinstance(graph, str) and graph.strip():
                    raw_title = node.get("title")
                    if not raw_title:
                        layout = node.get("layout") or {}
                        t = layout.get("title")
                        raw_title = t.get("text") if isinstance(t, dict) else t
                    return {"graph": graph, "title": raw_title or ""}

            for v in node.values():
                r = _find_graph(v)
                if r:
                    return r

        elif isinstance(node, list):
            for item in node:
                r = _find_graph(item)
                if r:
                    return r
        return None

    for ev in events:
        found = _find_graph(ev)
        if not found:
            continue
        try:
            fig_obj = json.loads(found["graph"])
            if not isinstance(fig_obj.get("data"), list):
                continue

            layout = fig_obj.get("layout") or {}
            title_from_layout = ""
            lt = layout.get("title")
            if isinstance(lt, str):
                title_from_layout = lt
            elif isinstance(lt, dict):
                title_from_layout = lt.get("text", "")

            return {
                "title": found.get("title") or title_from_layout or "그래프",
                "fig": {
                    "data": fig_obj["data"],
                    "layout": layout,
                    "config": fig_obj.get("config") or {},
                    "frames": fig_obj.get("frames")
                    if isinstance(fig_obj.get("frames"), list)
                    else None,
                },
            }
        except (json.JSONDecodeError, KeyError, TypeError):
            continue

    return None


# ── assistant text ─────────────────────────────────────────


def extract_assistant_text(events: Any) -> str:
    """Extract model-role text parts from ADK events (skip thought parts)."""
    if not isinstance(events, list):
        return ""
    texts: list[str] = []
    for ev in events:
        content = ev.get("content") or {}
        if content.get("role") != "model":
            continue
        for p in content.get("parts") or []:
            t = (p.get("text") or "").strip()
            if not t:
                continue
            if p.get("thought"):
                continue
            texts.append(t)
    return "\n".join(texts).strip()


# ── plotly URL extraction ─────────────────────────────────────

# MCP resource URL 패턴: mcp://resource/xxx.json 또는 http(s)://...mcp://resource/xxx.json
_PLOTLY_URL_PATTERN = re.compile(
    r'https?://[^\s\)]+mcp://resource/[a-f0-9]+\.json|mcp://resource/[a-f0-9]+\.json',
    re.IGNORECASE
)


def extract_plotly_urls(text: str) -> list[str]:
    """Extract Plotly JSON URLs from assistant text.

    Matches patterns like:
    - https://adk-resource-host.com/mcp://resource/abc123.json
    - mcp://resource/abc123.json
    """
    if not text:
        return []
    return _PLOTLY_URL_PATTERN.findall(text)
