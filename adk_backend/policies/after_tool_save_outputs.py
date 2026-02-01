import os
import json
import base64
from typing import Optional, Any, Dict, Tuple, List

from google.adk.tools.base_tool import BaseTool
from google.adk.tools.tool_context import ToolContext
from google.genai import types

from mcp import types as mcp_types
from mcp import ClientSession
from mcp.client.streamable_http import streamable_http_client

from ..utils.bytes_parser import _to_bytes_from_part


STATE_LAST_TOOL_RUNS = "workspace:last_tool_runs"   # 최근 실행 기록
STATE_ARTIFACT_INDEX = "workspace:artifact_index"   # 결과 아티팩트 인덱스


# -------------------------
# 1) Decode tool result
# -------------------------

def decode_tool_result(tool_response: Any) -> Optional[Dict[str, Any]]:
    """툴 응답을 표준 {status, outputs:[...]} 형태로 최대한 복원."""
    if not tool_response or not isinstance(tool_response, dict):
        return None

    structured = tool_response.get("structuredContent", None)
    if isinstance(structured, dict):
        if structured.get("status") and isinstance(structured.get("outputs"), list):
            return structured
        if structured.get("status") == "success" and "uri" in structured:
            return {"status": "success", "outputs": [structured]}

    content_list = tool_response.get("content", [])
    if isinstance(content_list, list) and content_list:
        text_data = content_list[0].get("text")
        if isinstance(text_data, str) and text_data.strip():
            try:
                return json.loads(text_data)
            except Exception:
                return None

    return None


# -------------------------
# 2) MCP resource fetch + bytes
# -------------------------

async def fetch_mcp_part0(uri: str) -> Optional[mcp_types.ResourceContents]:
    """MCP 서버에서 resource contents[0]을 가져온다."""
    try:
        async with streamable_http_client(os.getenv("MCP_SERVER_URL")) as (read_stream, write_stream, _):
            async with ClientSession(read_stream, write_stream) as session:
                await session.initialize()
                rr = await session.read_resource(uri)
                if rr and rr.contents:
                    return rr.contents[0]
    except Exception:
        return None
    return None


def decode_output_bytes(output: Dict[str, Any], part0: Optional[mcp_types.ResourceContents]) -> Tuple[Optional[bytes], str]:
    """resource_link output에서 raw bytes를 얻는다. (1) MCP part0 → (2) base64 fallback."""
    # mime 추정(표준/변형 키 모두 허용)
    mime_type = output.get("mime_type") or output.get("mimeType") or "application/octet-stream"

    # 1) MCP contents → bytes
    if part0 is not None:
        try:
            raw = _to_bytes_from_part(part0)
            if raw:
                return raw, mime_type
        except Exception:
            pass

    # 2) base64 fallback
    b64 = output.get("data_base64")
    if isinstance(b64, str) and b64:
        try:
            raw = base64.b64decode(b64)
            # state/artifact에 base64 남기지 않기
            output.pop("data_base64", None)
            return raw, mime_type
        except Exception:
            return None, mime_type

    return None, mime_type


# -------------------------
# 3) Artifact save
# -------------------------

async def save_bytes_as_artifact(
    tool_context: ToolContext,
    raw_bytes: bytes,
    filename: str,
    mime_type: str,
) -> Any:
    """bytes를 ADK artifact로 저장하고 version을 반환."""
    part = types.Part(
        inline_data=types.Blob(
            data=raw_bytes,
            mime_type=mime_type,
        )
    )
    version = await tool_context.save_artifact(filename=filename, artifact=part)
    return version


# -------------------------
# 4) State 기록(최소 정보만)
# -------------------------

def _shrink_args_for_state(args: Dict[str, Any]) -> Dict[str, Any]:
    """state 저장용으로 args를 축약. 대용량/민감/불필요 필드를 제거."""
    if not isinstance(args, dict):
        return {}

    slim = dict(args)

    # ✅ direct 입력이면 data는 절대 state에 저장하지 않음
    if slim.get("kind") == "direct":
        if "data" in slim:
            slim["data"] = "<omitted:direct_data>"
    # locator면 locator 자체는 작으니 유지(단, session_id/version은 callback이 채웠을 수도 있으니 유지 가능)
    # 필요시 여기서도 더 축약 가능

    # 너무 긴 텍스트 필드 컷(예: prompt 같은 게 들어오면)
    for k, v in list(slim.items()):
        if isinstance(v, str) and len(v) > 500:
            slim[k] = v[:500] + "...<truncated>"

    return slim


def append_tool_run_state(
    tool_context: ToolContext,
    *,
    tool_name: str,
    args: Dict[str, Any],
    outputs_saved: List[Dict[str, Any]],
) -> None:
    """최근 툴 실행 기록을 state에 append."""
    run_rec = {
        "tool_name": tool_name,
        "call_id": getattr(tool_context, "function_call_id", None) or getattr(tool_context, "invocation_id", None),
        "args": _shrink_args_for_state(args),
        "outputs": outputs_saved,  # [{artifact_filename, artifact_version, mime_type, description, source_uri, ...}]
    }

    last = tool_context.state.get(STATE_LAST_TOOL_RUNS, [])
    if not isinstance(last, list):
        last = []
    last.append(run_rec)
    tool_context.state[STATE_LAST_TOOL_RUNS] = last[-30:]  # 최근 30회만

    idx = tool_context.state.get(STATE_ARTIFACT_INDEX, [])
    if not isinstance(idx, list):
        idx = []
    idx.extend(outputs_saved)
    tool_context.state[STATE_ARTIFACT_INDEX] = idx[-200:]


# -------------------------
# 5) Main callback
# -------------------------

async def after_tool_save_outputs(
    tool: BaseTool,
    args: Dict[str, Any],
    tool_context: ToolContext,
    tool_response: Any,
) -> Optional[Dict[str, Any]]:
    """MCP resource_link 결과를 ADK artifact로 저장하고 state에 실행기록을 남긴다."""
    decoded = decode_tool_result(tool_response)
    if not decoded or not isinstance(decoded.get("outputs"), list):
        return None

    tool_name = getattr(tool, "name", None) or tool.__class__.__name__

    outputs_saved: List[Dict[str, Any]] = []
    changed = False

    for output in decoded["outputs"]:
        if not isinstance(output, dict):
            continue

        if output.get("type") != "resource_link":
            continue

        uri = output.get("uri")
        if not isinstance(uri, str) or not uri.strip():
            continue

        filename = output.get("filename") or output.get("name") or f"output_{tool_context.function_call_id}.bin"

        # 1) MCP에서 part0 로드
        part0 = await fetch_mcp_part0(uri)

        # 2) bytes 복원
        raw_bytes, mime_type = decode_output_bytes(output, part0)
        if not raw_bytes:
            continue

        # 3) artifact 저장
        version = await save_bytes_as_artifact(tool_context, raw_bytes, filename, mime_type)

        ext = None
        if isinstance(filename, str) and "." in filename:
            ext = filename.rsplit(".", 1)[-1].lower()

        # 4) output에 artifact 메타 추가(툴 응답 자체도 “주소화”)
        output["artifact_filename"] = filename
        output["artifact_version"] = version
        output["mime_type"] = mime_type  # 정규화

        outputs_saved.append(
            {
                "tool_name": tool_name,
                "source_uri": uri,
                "mime_type": mime_type,
                "ext": ext, 
                "description": output.get("description", ""),
                "artifact_filename": filename,
                "artifact_version": int(version) if version is not None else version,
            }
        )

        changed = True

    # 5) state 기록은 “툴 호출/입력/출력”만
    if outputs_saved:
        append_tool_run_state(tool_context, tool_name=tool_name, args=args, outputs_saved=outputs_saved)

    return decoded if changed else None
