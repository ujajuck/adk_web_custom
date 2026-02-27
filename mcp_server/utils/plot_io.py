"""
plot_toolbox 공통 IO + Wrapper.

- raw_args(dict) -> DataSource(Direct|Artifact|File) 검증
- -> DataFrame 로딩(또는 변환)
- -> core_fn 실행(기존 plot 로직을 최대한 유지)
- -> 결과를 MCP resource store에 저장 (json/png/html/csv 등)
- -> 표준 ToolResponse 반환 (outputs 리스트)

지원 입력 형태:
- source_type="direct": 데이터 직접 전달
- source_type="artifact": ADK 아티팩트에서 로드 (artifact_name + columns)
- source_type="file": 로컬 파일에서 로드 (path + columns)
- 하위 호환: kind="direct"|"locator" 형식도 지원
"""

from __future__ import annotations

import json
import re
import uuid
from typing import Any, Dict, Optional, Tuple, Callable

import pandas as pd

from ..utils.model import (
    build_error_response,
)
from ..utils.path_resolver import save_resource, save_resource_bytes
from ..utils.data_source import (
    resolve_dataframe_from_args,
)


_SAFE_CHARS = re.compile(r"[^a-zA-Z0-9_\-\.]+")


def make_job_id() -> str:
    """job_id 생성."""
    return uuid.uuid4().hex


def make_safe_title(title: str, fallback: str = "result") -> str:
    """파일명에 안전한 제목으로 정규화."""
    t = (title or "").strip() or fallback
    t = t.replace(" ", "_")
    t = _SAFE_CHARS.sub("_", t)
    return t[:120]


def resolve_input_to_dataframe(
    raw_args: Dict[str, Any],
    context: Optional[Any] = None,
) -> Tuple[pd.DataFrame, Optional[list]]:
    """raw_args를 해석하여 DataFrame으로 통일.

    지원 입력 형태:
    - source_type="direct": 데이터 직접 전달
    - source_type="artifact": ADK 아티팩트에서 로드 (artifact_name + columns)
    - source_type="file": 로컬 파일에서 로드 (path + columns)
    - 하위 호환: kind="direct"|"locator" 형식도 지원

    Args:
        raw_args: 툴 입력 딕셔너리
        context: 툴 컨텍스트 (아티팩트 로드 시 session_id 등 주입용)

    Returns:
        (df, columns): columns는 사용자가 지정한 컬럼 리스트(없으면 None)
    """
    return resolve_dataframe_from_args(raw_args, context)


def _ensure_bytes_for_json(obj: Any) -> bytes:
    """dict/list/기타 JSON 직렬화 가능한 객체를 UTF-8 bytes로 변환."""
    if isinstance(obj, (bytes, bytearray)):
        return bytes(obj)
    return json.dumps(obj, ensure_ascii=False, indent=2).encode("utf-8")


def _build_outputs_success(outputs: list[dict]) -> Dict[str, Any]:
    """outputs 여러 개를 포함한 success 응답 생성."""
    # build_success_response가 단일 output만 만든다면, model.py 쪽을
    # build_success_response(outputs=[...]) 형태로 확장하는 게 가장 깔끔.
    # 여기서는 'outputs'를 직접 감싸는 방식으로 최소 침습 구현.
    return {"status": "success", "outputs": outputs}


def save_outputs_and_build_response(
    *,
    job_id: str,
    title: str,
    description: str,
    payloads: Dict[str, Any],
) -> Dict[str, Any]:
    """payloads에 들어있는 여러 산출물(json/png/html/csv)을 저장하고 outputs 리스트로 반환.

    payloads 예:
      {"json": <dict|bytes>, "png": <bytes>, "html": <bytes>}
      {"csv": <DataFrame>}
      {"json": <dict>}  # 단일도 OK
    """
    safe_title = make_safe_title(title)
    outputs: list[dict] = []

    # 저장 순서(프론트에서 우선 표시 용): json -> png -> html -> csv
    for ext in ["json", "png", "html", "csv"]:
        if ext not in payloads:
            continue

        obj = payloads[ext]

        if ext in ("png", "html"):
            if not isinstance(obj, (bytes, bytearray)):
                raise ValueError(f"{ext} 출력은 bytes 여야 합니다.")
            uri, stored_filename, mime_type = save_resource_bytes(bytes(obj), job_id=job_id, ext=ext)
            display_filename = f"{safe_title}.{ext}"
            outputs.append(
                {
                    "type": "resource_link",
                    "uri": uri,
                    "filename": display_filename,
                    "mime_type": mime_type,
                    "description": description if ext == "json" else f"{description} ({ext})",
                }
            )
            continue

        if ext == "json":
            # dict/list 등 -> bytes로 저장
            data_bytes = _ensure_bytes_for_json(obj)
            uri, stored_filename, mime_type = save_resource_bytes(data_bytes, job_id=job_id, ext="json")
            display_filename = f"{safe_title}.json"
            outputs.append(
                {
                    "type": "resource_link",
                    "uri": uri,
                    "filename": display_filename,
                    "mime_type": mime_type,
                    "description": description,
                }
            )
            continue

        if ext == "csv":
            # csv는 기존 save_resource 유지(DF 보장)
            uri, stored_filename, mime_type = save_resource(obj, job_id=job_id, ext="csv")
            display_filename = f"{safe_title}.csv"
            outputs.append(
                {
                    "type": "resource_link",
                    "uri": uri,
                    "filename": display_filename,
                    "mime_type": mime_type,
                    "description": description,
                }
            )
            continue

    return _build_outputs_success(outputs)


def safe_run_tool(
    *,
    raw_args: Dict[str, Any],
    core_fn: Callable[[pd.DataFrame, Optional[list], Dict[str, Any]], Tuple[Any, Dict[str, Any]]],
    title: str,
    ext: str,
    description_builder: Callable[[pd.DataFrame, Any, Dict[str, Any]], str],
    context: Optional[Any] = None,
) -> Dict[str, Any]:
    """표준 Wrapper: 입력→DF→core 실행→리소스 저장→표준 응답.

    지원 입력 형태:
    - source_type="direct": 데이터 직접 전달
    - source_type="artifact": ADK 아티팩트에서 로드 (artifact_name + columns)
    - source_type="file": 로컬 파일에서 로드 (path + columns)
    - 하위 호환: kind="direct"|"locator" 형식도 지원

    Args:
        raw_args: 툴 입력 딕셔너리
        core_fn: 핵심 로직 함수 (df, columns, raw_args) -> (result_obj, meta)
        title: 결과 파일 제목
        ext: 결과 파일 확장자 ("json"|"csv")
        description_builder: 설명 생성 함수 (df, result_obj, meta) -> str
        context: 툴 컨텍스트 (아티팩트 로드 시 session_id 등 주입용)

    core_fn 반환:
      - (result_obj, meta)
        - 단일 결과: ext 파라미터로 저장 (기존 방식)
      - (payloads_dict, meta)
        - payloads_dict 예: {"json": <dict|bytes>, "png": <bytes>, "html": <bytes>}
    """
    try:
        job_id = make_job_id()
        df, columns = resolve_input_to_dataframe(raw_args, context)

        result_obj, meta = core_fn(df, columns, raw_args)
        description = description_builder(df, result_obj, meta)

        # ✅ 멀티 산출물 지원: dict에 json/png/html/csv 키가 있으면 멀티 저장
        if isinstance(result_obj, dict) and any(k in result_obj for k in ("json", "png", "html", "csv")):
            return save_outputs_and_build_response(
                job_id=job_id,
                title=title,
                description=description,
                payloads=result_obj,
            )

        # ✅ 기존 단일 저장(하위 호환)
        # ext는 "csv"|"json" 을 기존대로 사용
        if ext == "json":
            payloads = {"json": result_obj}
        elif ext == "csv":
            payloads = {"csv": result_obj}
        else:
            raise ValueError(f"지원하지 않는 ext 입니다: {ext}")

        return save_outputs_and_build_response(
            job_id=job_id,
            title=title,
            description=description,
            payloads=payloads,
        )

    except Exception as e:
        return build_error_response(message=str(e))
