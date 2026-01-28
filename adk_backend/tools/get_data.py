import os
from pathlib import Path
from typing import Any, Dict, Optional

from google.adk.tools import ToolContext   
from google.genai import types        

DEFAULT_CSV_PATH = os.getenv("DEFAULT_CSV_PATH", "").strip()


def _validate_csv_path(csv_path: str) -> Path:
    """CSV 파일 경로를 검증하고 Path로 반환"""
    if not csv_path or not csv_path.strip():
        raise ValueError("path가 비어있습니다. path를 주거나 DEFAULT_CSV_PATH를 설정하세요.")
    p = Path(csv_path).expanduser().resolve()
    if not p.exists():
        raise FileNotFoundError(f"파일이 존재하지 않습니다: {p}")
    if not p.is_file():
        raise ValueError(f"파일 경로가 아닙니다: {p}")
    if p.suffix.lower() != ".csv":
        raise ValueError(f"CSV(.csv)만 허용됩니다: {p.name}")
    return p


async def load_csv_from_path_and_save_artifact(
    path: Optional[str] = None,
    artifact_name: str = "input.csv",
    mime_type: str = "text/csv",
    size_limit_bytes: int = 50 * 1024 * 1024,
    tool_context: ToolContext = None, 
) -> Dict[str, Any]:
    """
    로컬 경로의 CSV 파일을 읽어 ADK 아티팩트로 저장한다.

    Args:
        path (Optional[str]): CSV 파일 경로. 미지정 시 DEFAULT_CSV_PATH 사용.
        artifact_name (str): 아티팩트에 저장될 파일명.
        mime_type (str): MIME 타입(기본 text/csv).
        size_limit_bytes (int): 파일 크기 제한(기본 50MB).
        tool_context (ToolContext): ADK가 런타임에 주입하는 컨텍스트.

    Returns:
        Dict[str, Any]:
            - ok (bool)
            - filename (str)
            - version (Any): save_artifact 반환(버전/locator는 ADK 버전별로 다를 수 있음)
            - bytes (int)
            - source_path (str)
    """
    if tool_context is None:
        raise ValueError("tool_context가 주입되지 않았습니다. Agent tools에 함수가 등록되어야 합니다.")

    csv_path = (path or DEFAULT_CSV_PATH).strip()
    p = _validate_csv_path(csv_path)

    blob = p.read_bytes()
    if len(blob) > size_limit_bytes:
        raise ValueError(f"파일이 너무 큽니다: {len(blob)} > {size_limit_bytes} bytes")

    artifact_part = types.Part(
        inline_data=types.Blob(
            mime_type=mime_type,
            data=blob,
            display_name=artifact_name,
        )
    )
    version = await tool_context.save_artifact(filename=artifact_name, artifact=artifact_part)

    return {
        "ok": True,
        "filename": artifact_name,
        "version": version,
        "bytes": len(blob),
        "source_path": str(p),
    }
