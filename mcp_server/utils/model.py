from __future__ import annotations

from typing import Any, Dict, List, Literal, Optional, Union
from pydantic import BaseModel, ConfigDict, Field


# -------------------------
# Input Contracts
# -------------------------

class ArtifactLocator(BaseModel):
    """ADK artifact_locator(dict)의 표준 형태.

    Parameters:
        session_id (str): ADK session id
        artifact_name (str): 아티팩트 이름(폴더명)
        version (int): 아티팩트 버전(0 이상)
        file_name (Optional[str]): 실제 파일명(미지정 시 artifact_name 사용)

    Returns:
        ArtifactLocator: 검증/정규화된 locator
    """
    model_config = ConfigDict(extra="ignore")

    session_id: Optional[str] = Field(..., description="ADK session id")
    artifact_name: str = Field(..., description="artifact folder/name")
    version: Optional[int] = Field(..., ge=0, description="artifact version >= 0")
    file_name: Optional[str] = Field(default=None, description="artifact file name (optional)")


class DirectDataInput(BaseModel):
    """직접 데이터 입력(작은 데이터 권장).

    Parameters:
        data (Any): JSON-serializable 객체(list[dict], dict 등)
        columns (Optional[List[str]]): 사용할 컬럼명 목록(옵션)

    Returns:
        DirectDataInput
    """
    model_config = ConfigDict(extra="ignore")

    kind: Literal["direct"] = "direct"
    data: Any = Field(..., description="direct data(JSON-serializable)")
    columns: Optional[List[str]] = Field(default=None, description="columns to use (optional)")


class LocatorDataInput(BaseModel):
    """artifact_locator로 ADK 저장공간에서 파일을 찾아 읽는 입력.

    Parameters:
        artifact_locator (ArtifactLocator): ADK artifact locator
        columns (Optional[List[str]]): 사용할 컬럼명 목록(옵션)

    Returns:
        LocatorDataInput
    """
    model_config = ConfigDict(extra="ignore")

    kind: Literal["locator"] = "locator"
    artifact_locator: ArtifactLocator = Field(..., description="ADK artifact locator")
    columns: Optional[List[str]] = Field(default=None, description="columns to use (optional)")


ToolInput = Union[DirectDataInput, LocatorDataInput]


# -------------------------
# Output Contracts
# -------------------------

class ResourceLinkOutput(BaseModel):
    """MCP 리소스 저장소 결과 링크."""
    model_config = ConfigDict(extra="ignore")

    type: Literal["resource_link"] = "resource_link"
    uri: str
    filename: str
    mime_type: str
    description: str


class ErrorOutput(BaseModel):
    """실패 응답 item."""
    model_config = ConfigDict(extra="ignore")

    message: str


class ToolResponse(BaseModel):
    """표준 응답."""
    model_config = ConfigDict(extra="ignore")

    status: Literal["success", "error"]
    outputs: List[Union[ResourceLinkOutput, ErrorOutput]]


def build_success_response(*, uri: str, filename: str, mime_type: str, description: str) -> Dict[str, Any]:
    """성공 표준 응답(dict) 생성."""
    resp = ToolResponse(
        status="success",
        outputs=[ResourceLinkOutput(uri=uri, filename=filename, mime_type=mime_type, description=description)],
    )
    return resp.model_dump()


def build_error_response(*, message: str) -> Dict[str, Any]:
    """실패 표준 응답(dict) 생성."""
    resp = ToolResponse(status="error", outputs=[ErrorOutput(message=message)])
    return resp.model_dump()