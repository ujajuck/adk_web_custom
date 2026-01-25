import os
from pathlib import Path
from typing import Any, Dict, Optional

# ADK 버전에 따라 import 경로가 다를 수 있습니다.
# 보통 아래 중 하나를 씁니다.
# from google.adk.tools import tool
# from google.adk.tools.tool import tool
from google.adk.tools.tool_context import ToolContext


# DEFAULT_CSV_PATH = os.getenv("DEFAULT_CSV_PATH", "").strip()
DEFAULT_CSV_PATH = "C:/MyFolder/data/pokemon.csv"

def _validate_csv_path(csv_path: str) -> Path:
    """입력 경로를 검증하고 Path로 반환"""
    if not csv_path or not csv_path.strip():
        raise ValueError("csv_path가 비어있습니다. path를 입력하거나 DEFAULT_CSV_PATH 환경변수를 설정하세요.")

    p = Path(csv_path).expanduser().resolve()
    if not p.exists():
        raise FileNotFoundError(f"파일이 존재하지 않습니다: {p}")
    if not p.is_file():
        raise ValueError(f"파일 경로가 아닙니다: {p}")
    if p.suffix.lower() != ".csv":
        raise ValueError(f"CSV(.csv) 파일만 허용됩니다: {p.name}")
    return p


async def load_csv_from_path_and_save_artifact(
    tool_context: ToolContext,
    path: Optional[str] = None,
    artifact_name: str = "input.csv",
    mime_type: str = "text/csv",
    size_limit_bytes: int = 50 * 1024 * 1024,
) -> Dict[str, Any]:
    """
    로컬 경로의 CSV 파일을 읽어 ADK 아티팩트로 저장한다.

    Args:
        tool_context (ToolContext): ADK 툴 컨텍스트(아티팩트 저장에 사용).
        path (Optional[str]): 읽을 CSV 파일 경로. 미지정 시 DEFAULT_CSV_PATH 환경변수 사용.
        artifact_name (str): 아티팩트에 저장될 파일명(기본: input.csv).
        mime_type (str): MIME 타입(기본: text/csv).
        size_limit_bytes (int): 파일 크기 제한(기본: 50MB).

    Returns:
        Dict[str, Any]: 저장 결과.
            - ok (bool)
            - artifact_locator (dict): 이후 tool에서 load_artifact 등에 재사용 가능한 식별자
            - bytes (int): 저장한 바이트 수
            - source_path (str): 원본 파일 경로
    """
    # 1) path 결정 (입력 우선, 없으면 DEFAULT_CSV_PATH)
    csv_path = (path or DEFAULT_CSV_PATH).strip()
    p = _validate_csv_path(csv_path)

    # 2) 파일 읽기 (바이너리로 읽어서 그대로 아티팩트에 저장)
    data = p.read_bytes()
    if len(data) > size_limit_bytes:
        raise ValueError(f"파일이 너무 큽니다: {len(data)} bytes > {size_limit_bytes} bytes")

    # 3) 아티팩트 저장
    # ADK 버전에 따라 save_artifact 시그니처가 조금 다를 수 있어,
    # 아래 형태가 안 맞으면 에러 메시지에 맞춰 파라미터명만 조정하면 됩니다.
    saved = await tool_context.save_artifact(
        filename=artifact_name,   # 아티팩트 내 파일명
        content=data,             # bytes
        mime_type=mime_type,
    )

    # 4) 반환 (saved가 locator를 포함하는 경우가 많음)
    # saved 형식이 ADK 버전에 따라 다를 수 있으니, locator를 최대한 안전하게 구성합니다.
    artifact_locator = None
    if isinstance(saved, dict) and "artifact_locator" in saved:
        artifact_locator = saved["artifact_locator"]
    elif isinstance(saved, dict):
        # 일부 버전은 dict 자체가 locator 역할을 하기도 함
        artifact_locator = saved
    else:
        # 최후의 보루: 최소 정보만 구성
        artifact_locator = {"filename": artifact_name}

    return {
        "ok": True,
        "artifact_locator": artifact_locator,
        "bytes": len(data),
        "source_path": str(p),
    }
