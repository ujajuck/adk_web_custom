from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Dict, Tuple

import pandas as pd
from dotenv import load_dotenv

load_dotenv("mcp_server/.env")

ADK_ARTIFACT_ROOT = os.environ.get("ADK_ARTIFACT_ROOT")
MCP_RESOURCE_ROOT = os.environ.get("MCP_RESOURCE_ROOT")


# -----------------------------
# ADK Artifact path resolver
# -----------------------------

def resolve_artifact_path(artifact_locator: Dict[str, Any]) -> str:
    """artifact_locator(dict) -> ADK 공용 저장소 내 실제 파일 절대경로(str)

    Parameters:
        artifact_locator (dict):
            필수: session_id(str), artifact_name(str), version(int|str)
            선택: file_name(str) - 없으면 artifact_name을 파일명으로 사용

    Returns:
        str: resolved absolute path

    Raises:
        ValueError: 필드 누락/루트 미설정/경로 이상(path traversal)
    """
    if not ADK_ARTIFACT_ROOT:
        raise ValueError("ADK_ARTIFACT_ROOT 환경변수가 설정되지 않았습니다.")

    try:
        session_id = artifact_locator["session_id"]
        artifact_name = artifact_locator["artifact_name"]
        version = str(artifact_locator["version"])
        file_name = artifact_locator.get("file_name", artifact_name)
    except KeyError as e:
        raise ValueError(f"artifact_locator 필드 누락: {e}")

    root = Path(ADK_ARTIFACT_ROOT).resolve()
    path = (
        root
        / "user"
        / "sessions"
        / session_id
        / "artifacts"
        / artifact_name
        / "versions"
        / version
        / file_name
    ).resolve()

    # path traversal 방어
    if root not in path.parents and path != root:
        raise ValueError("잘못된 artifact 경로입니다.")

    return str(path)


# -----------------------------
# MCP resource store helpers
# -----------------------------

_MIME_BY_EXT = {
    "csv": "text/csv",
    "json": "application/json",
    "png": "image/png",
    "html": "text/html",
    "htm": "text/html",
    "txt": "text/plain",
}


def _get_mime_type(ext: str) -> str:
    """확장자에 대응하는 mime_type 반환. 미등록이면 application/octet-stream."""
    e = (ext or "").lstrip(".").lower()
    return _MIME_BY_EXT.get(e, "application/octet-stream")


def get_mcp_resource_path(job_id: str, ext: str) -> Tuple[Path, str, str]:
    """MCP 리소스 저장 경로(Path)와 URI, mime_type을 만든다.

    Parameters:
        job_id (str): 결과 식별자(파일명 prefix)
        ext (str): 'csv'|'json'|'png'|'html' 등 (점 제외 권장)

    Returns:
        (abs_path, uri, mime_type)
          - abs_path: 실제 저장할 절대 경로(Path)
          - uri: mcp://resource/<job_id>.<ext>
          - mime_type: 확장자 기반 mime (미등록이면 application/octet-stream)

    Raises:
        ValueError: MCP_RESOURCE_ROOT 미설정
    """
    if not MCP_RESOURCE_ROOT:
        raise ValueError("MCP_RESOURCE_ROOT 환경변수가 설정되지 않았습니다.")

    root = Path(MCP_RESOURCE_ROOT).resolve()
    root.mkdir(parents=True, exist_ok=True)

    safe_ext = (ext or "").lstrip(".").lower()
    if not safe_ext:
        raise ValueError("ext가 비어있습니다.")

    abs_path = (root / f"{job_id}.{safe_ext}").resolve()
    # root 밖으로 나가지 않도록 방어(이론상 job_id에 '../' 들어오는 경우)
    if root not in abs_path.parents and abs_path != root:
        raise ValueError("잘못된 MCP resource 경로입니다.")

    uri = f"mcp://resource/{abs_path.name}"
    mime = _get_mime_type(safe_ext)
    return abs_path, uri, mime


def save_resource_bytes(data: bytes, job_id: str, ext: str) -> Tuple[str, str, str]:
    """bytes를 MCP resource store에 저장 후 (uri, filename, mime_type) 반환.

    Parameters:
        data (bytes): 저장할 바이트 데이터
        job_id (str): 결과 식별자
        ext (str): 확장자 (json/png/html/csv 등)

    Returns:
        (uri, filename, mime_type)
    """
    abs_path, uri, mime = get_mcp_resource_path(job_id=job_id, ext=ext)
    abs_path.parent.mkdir(parents=True, exist_ok=True)
    abs_path.write_bytes(data)
    return uri, abs_path.name, mime


def save_resource(obj: Any, job_id: str, ext: str) -> Tuple[str, str, str]:
    """(편의/호환) obj를 MCP resource store에 저장 후 (uri, filename, mime_type) 반환.

    - csv: pandas.DataFrame만 지원
    - json: dict/list 등 JSON 직렬화 가능한 객체

    PNG/HTML 등은 save_resource_bytes()를 사용하세요.

    Parameters:
        obj: pd.DataFrame 또는 dict/list 등
        job_id (str): 결과 식별자
        ext (str): "csv"|"json"

    Returns:
        (uri, filename, mime_type)
    """
    safe_ext = (ext or "").lstrip(".").lower()
    abs_path, uri, mime = get_mcp_resource_path(job_id=job_id, ext=safe_ext)

    if safe_ext == "csv":
        if not isinstance(obj, pd.DataFrame):
            raise ValueError("csv 저장은 pandas.DataFrame만 지원합니다.")
        with abs_path.open("w", encoding="utf-8-sig", newline="") as f:
            obj.to_csv(f, index=False, lineterminator="\r\n", na_rep="null")
        return uri, abs_path.name, mime

    if safe_ext == "json":
        with abs_path.open("w", encoding="utf-8") as f:
            json.dump(obj, f, ensure_ascii=False, indent=2)
        return uri, abs_path.name, mime

    raise ValueError(f"save_resource는 csv/json만 지원합니다. ext={safe_ext} 는 save_resource_bytes를 사용하세요.")
