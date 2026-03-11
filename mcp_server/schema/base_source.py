"""공통 데이터 소스 기본 클래스.

모든 차트 Request에서 공통으로 사용하는 소스 타입 정의.
차트별로 DirectSource는 데이터 형식이 다르므로 각 Request에서 별도 정의.
"""
from __future__ import annotations

from typing import Any, Dict, List, Literal, Optional

import pandas as pd
from pydantic import BaseModel, ConfigDict, Field

from ..utils.path_resolver import get_artifact_path


class ArtifactSource(BaseModel):
    """ADK 아티팩트에서 데이터를 로드하는 소스.

    ADK callback이 user_id, session_id를 자동으로 주입합니다.
    """
    model_config = ConfigDict(extra="ignore")

    source_type: Literal["artifact"] = "artifact"
    artifact_name: str = Field(..., description="아티팩트 파일명 (예: pokemon.csv)")
    user_id: Optional[str] = Field(None, description="사용자 ID (ADK callback이 자동 주입)")
    session_id: Optional[str] = Field(None, description="세션 ID (ADK callback이 자동 주입)")
    version: int = Field(0, description="아티팩트 버전")
    columns: Optional[List[str]] = Field(None, description="사용할 컬럼 목록")

    def resolve_dataframe(self) -> pd.DataFrame:
        """아티팩트 파일을 DataFrame으로 로드."""
        if not self.user_id or not self.session_id:
            raise ValueError(
                "user_id와 session_id가 필요합니다. "
                "ADK callback이 자동 주입하도록 설정되어 있는지 확인하세요."
            )

        csv_path = get_artifact_path(
            user_id=self.user_id,
            session_id=self.session_id,
            artifact_name=self.artifact_name,
            version=self.version,
        )

        df = pd.read_csv(csv_path)
        if self.columns:
            available = [c for c in self.columns if c in df.columns]
            if available:
                df = df[available]
        return df


class FileSource(BaseModel):
    """로컬 파일에서 데이터를 로드하는 소스."""
    model_config = ConfigDict(extra="ignore")

    source_type: Literal["file"] = "file"
    path: str = Field(..., description="파일 경로")
    columns: Optional[List[str]] = Field(None, description="사용할 컬럼 목록")

    def resolve_dataframe(self) -> pd.DataFrame:
        """파일을 DataFrame으로 로드."""
        df = pd.read_csv(self.path)
        if self.columns:
            available = [c for c in self.columns if c in df.columns]
            if available:
                df = df[available]
        return df


class TabularDirectSource(BaseModel):
    """테이블 형식 데이터를 직접 전달하는 소스.

    Histogram, BarPlot, ScatterPlot, PieChart 등에서 사용.
    """
    model_config = ConfigDict(extra="ignore")

    source_type: Literal["direct"] = "direct"
    data: List[Dict[str, Any]] = Field(..., description="데이터 레코드 목록")

    def resolve_dataframe(self) -> pd.DataFrame:
        """데이터를 DataFrame으로 변환."""
        if not self.data:
            raise ValueError("data가 비어있습니다.")
        return pd.DataFrame(self.data)


def resolve_dataframe(source: Dict[str, Any]) -> pd.DataFrame:
    """소스 딕셔너리에서 DataFrame을 로드하는 헬퍼 함수.

    Args:
        source: 소스 설정 딕셔너리
            - source_type: "direct", "artifact", "file" 중 하나

    Returns:
        pd.DataFrame: 로드된 데이터프레임
    """
    if source is None:
        raise ValueError("source가 필요합니다.")

    source_type = source.get("source_type") or source.get("kind")

    if source_type == "direct":
        data = source.get("data", [])
        if not data:
            raise ValueError("data가 비어있습니다.")
        return pd.DataFrame(data)

    elif source_type == "artifact":
        artifact_source = ArtifactSource(**source)
        return artifact_source.resolve_dataframe()

    elif source_type == "file":
        file_source = FileSource(**source)
        return file_source.resolve_dataframe()

    elif source_type == "locator":
        # 하위 호환: 기존 locator 형식 지원
        locator = source.get("artifact_locator", {})
        artifact_source = ArtifactSource(
            source_type="artifact",
            artifact_name=locator.get("artifact_name") or locator.get("file_name"),
            user_id=source.get("user_id"),
            session_id=source.get("session_id"),
        )
        return artifact_source.resolve_dataframe()

    else:
        raise ValueError(f"지원하지 않는 source_type: {source_type}. direct|artifact|file 중 선택하세요.")
