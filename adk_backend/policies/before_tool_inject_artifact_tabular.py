# agent/policies/before_tool_inject_artifact_tabular.py

from __future__ import annotations

import io
from typing import Any, Dict, List, Optional

import pandas as pd

from google.adk.tools.base_tool import BaseTool
from google.adk.tools.tool_context import ToolContext


def _extract_bytes_from_part(part: Any) -> Optional[bytes]:
    """
    ADK Artifact Part 에서 bytes 를 안전하게 추출한다.
    (text / inline_data 둘 다 대응)
    """
    text = getattr(part, "text", None)
    if isinstance(text, str) and text:
        return text.encode("utf-8")

    inline = getattr(part, "inline_data", None)
    if inline is not None:
        data = getattr(inline, "data", None)
        if isinstance(data, (bytes, bytearray)) and data:
            return bytes(data)

    return None


async def before_tool_inject_artifact_tabular(
    tool: BaseTool,
    args: Dict[str, Any],
    tool_context: ToolContext,
) -> Optional[Dict[str, Any]]:
    """
    CSV artifact -> List[Dict] 로 변환하여 MCP 툴 인자에 주입한다.

    동작 조건:
    - args 에 'artifact_filename' 이 있을 때만 동작
    - 이미 data 가 있으면 건드리지 않음
    """

    artifact_filename = args.get("artifact_filename")
    if not isinstance(artifact_filename, str) or not artifact_filename.strip():
        return None 

    if not artifact_filename.lower().endswith((".csv", ".tsv")):
        return None

    # 주입할 파라미터 이름 (기본: data)
    data_param = args.get("data_param") or "data"

    # 이미 data 가 있으면 그대로 둔다 (강제 덮어쓰기 원하면 이 줄 삭제)
    if isinstance(args.get(data_param), list):
        return None

    # --- ADK Artifact 로드 ---
    part = await tool_context.load_artifact(filename=artifact_filename)
    if part is None:
        raise ValueError(f"artifact not found: {artifact_filename}")

    raw_bytes = _extract_bytes_from_part(part)
    if not raw_bytes:
        raise ValueError(f"artifact has no readable payload: {artifact_filename}")

    # 옵션 처리
    max_rows = args.get("max_rows", 5000)
    try:
        max_rows = int(max_rows)
    except Exception:
        max_rows = 5000

    usecols = args.get("usecols")
    if usecols is not None and not isinstance(usecols, list):
        usecols = None

    sep = args.get("sep")
    if sep is not None and not isinstance(sep, str):
        sep = None

    # --- CSV → records ---
    df = pd.read_csv(io.BytesIO(raw_bytes), usecols=usecols, sep=sep)
    if max_rows > 0 and len(df) > max_rows:
        df = df.head(max_rows)

    records: List[Dict[str, Any]] = df.to_dict(orient="records")

    # --- args 주입 ---
    new_args = dict(args)
    new_args[data_param] = records

    # 디버깅/추적용 메타
    new_args["_source_artifact"] = artifact_filename
    new_args["_rows"] = len(records)
    new_args["_cols"] = list(df.columns)

    return new_args
