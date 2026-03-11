"""데이터 소스 모델 및 로더.

여러 입력 형태(아티팩트, 파일, 직접 입력)를 통일된 인터페이스로 처리한다.
각 소스 타입은 resolve_dataframe() 메서드로 DataFrame을 반환한다.

사용 예:
    # 아티팩트에서 로드
    source = ArtifactSource(
        source_type="artifact",
        artifact_name="sales_data",
        columns=["date", "revenue", "cost"],
    )
    df = source.resolve_dataframe(tool_context)

    # 파일에서 로드
    source = FileSource(
        source_type="file",
        path="C:/data/sales.csv",
        columns=["date", "revenue"],
    )
    df = source.resolve_dataframe()

    # 직접 입력
    source = DirectSource(
        source_type="direct",
        data=[{"x": 1, "y": 2}, {"x": 3, "y": 4}],
        columns=["x", "y"],
    )
    df = source.resolve_dataframe()
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Dict, List, Literal, Optional, Union
from abc import ABC, abstractmethod

import pandas as pd
from pydantic import BaseModel, ConfigDict, Field, model_validator

from .path_resolver import resolve_artifact_path, ADK_ARTIFACT_ROOT


# =============================================================================
# Base Source Model
# =============================================================================

class BaseDataSource(BaseModel, ABC):
    """데이터 소스 기본 클래스.

    모든 소스 타입은 이 클래스를 상속하고 resolve_dataframe()을 구현해야 한다.
    """
    model_config = ConfigDict(extra="ignore")

    columns: Optional[List[str]] = Field(
        default=None,
        description="사용할 컬럼 목록. None이면 전체 컬럼 사용",
    )

    @abstractmethod
    def resolve_dataframe(self, context: Optional[Any] = None) -> pd.DataFrame:
        """소스에서 DataFrame을 로드한다.

        Args:
            context: 툴 컨텍스트 (아티팩트 로드 시 session_id 등 주입용)

        Returns:
            pd.DataFrame: 로드된 데이터프레임
        """
        pass

    def select_columns(self, df: pd.DataFrame) -> pd.DataFrame:
        """columns가 지정되어 있으면 해당 컬럼만 선택."""
        if self.columns:
            missing = [c for c in self.columns if c not in df.columns]
            if missing:
                raise ValueError(f"존재하지 않는 컬럼: {missing}. 사용 가능: {list(df.columns)}")
            return df[self.columns]
        return df


# =============================================================================
# Artifact Source
# =============================================================================

class ArtifactSource(BaseDataSource):
    """ADK 아티팩트에서 데이터를 로드하는 소스.

    artifact_name은 필수이며, session_id/version은 before_tool_callback에서 주입되거나
    직접 지정할 수 있다.

    사용 예:
        source = ArtifactSource(
            source_type="artifact",
            artifact_name="preprocessed_data",
            columns=["feature1", "feature2", "target"],
        )
        df = source.resolve_dataframe(tool_context)
    """
    source_type: Literal["artifact"] = Field(
        default="artifact",
        description="소스 타입 (discriminator)",
    )
    artifact_name: str = Field(
        ...,
        description="아티팩트 이름 (필수)",
    )
    session_id: Optional[str] = Field(
        default=None,
        description="세션 ID (미지정 시 컨텍스트에서 주입)",
    )
    version: Optional[int] = Field(
        default=None,
        ge=0,
        description="아티팩트 버전 (미지정 시 최신 버전 또는 컨텍스트에서 주입)",
    )
    file_name: Optional[str] = Field(
        default=None,
        description="파일명 (미지정 시 artifact_name 사용)",
    )

    @model_validator(mode="after")
    def _validate(self):
        if not self.artifact_name:
            raise ValueError("ArtifactSource는 artifact_name이 필수입니다.")
        return self

    def resolve_dataframe(self, context: Optional[Any] = None) -> pd.DataFrame:
        """아티팩트에서 DataFrame 로드.

        Args:
            context: 툴 컨텍스트. session_id/version이 없으면 컨텍스트에서 가져옴.

        Returns:
            pd.DataFrame
        """
        # session_id/version 결정
        session_id = self.session_id
        version = self.version

        # 컨텍스트에서 session_id/version 주입 시도
        if context is not None:
            if hasattr(context, "session_id") and not session_id:
                session_id = getattr(context, "session_id", None)
            if hasattr(context, "artifact_version") and version is None:
                version = getattr(context, "artifact_version", None)
            # state에서 가져오기 시도
            if hasattr(context, "state"):
                state = context.state
                if not session_id and hasattr(state, "get"):
                    session_id = state.get("session_id")
                if version is None and hasattr(state, "get"):
                    version = state.get("artifact_version", 0)

        if not session_id:
            raise ValueError(
                "ArtifactSource에 session_id가 필요합니다. "
                "직접 지정하거나 before_tool_callback에서 주입하세요."
            )
        if version is None:
            version = 0  # 기본값

        locator = {
            "session_id": session_id,
            "artifact_name": self.artifact_name,
            "version": version,
            "file_name": self.file_name or self.artifact_name,
        }

        path = resolve_artifact_path(locator)
        df = _read_data_file(path)
        return self.select_columns(df)


# =============================================================================
# File Source
# =============================================================================

class FileSource(BaseDataSource):
    """로컬 파일 경로에서 데이터를 로드하는 소스.

    CSV, JSON, Excel 파일을 지원한다.

    사용 예:
        source = FileSource(
            source_type="file",
            path="C:/data/sales.csv",
            columns=["date", "revenue"],
        )
        df = source.resolve_dataframe()
    """
    source_type: Literal["file"] = Field(
        default="file",
        description="소스 타입 (discriminator)",
    )
    path: str = Field(
        ...,
        description="파일 경로 (절대 또는 상대 경로)",
    )

    @model_validator(mode="after")
    def _validate(self):
        if not self.path:
            raise ValueError("FileSource는 path가 필수입니다.")
        return self

    def resolve_dataframe(self, context: Optional[Any] = None) -> pd.DataFrame:
        """파일에서 DataFrame 로드.

        Args:
            context: 사용되지 않음 (인터페이스 일관성 유지용)

        Returns:
            pd.DataFrame
        """
        if not Path(self.path).exists():
            raise FileNotFoundError(f"파일을 찾을 수 없습니다: {self.path}")

        df = _read_data_file(self.path)
        return self.select_columns(df)


# =============================================================================
# Direct Source
# =============================================================================

class DirectSource(BaseDataSource):
    """데이터를 직접 전달하는 소스.

    소량의 데이터나 이미 메모리에 있는 데이터에 적합하다.

    사용 예:
        source = DirectSource(
            source_type="direct",
            data=[{"x": 1, "y": 2}, {"x": 3, "y": 4}],
            columns=["x", "y"],
        )
        df = source.resolve_dataframe()
    """
    source_type: Literal["direct"] = Field(
        default="direct",
        description="소스 타입 (discriminator)",
    )
    data: Any = Field(
        ...,
        description="데이터 (list[dict], dict, DataFrame 등 JSON 직렬화 가능한 형태)",
    )

    @model_validator(mode="after")
    def _validate(self):
        if self.data is None:
            raise ValueError("DirectSource는 data가 필수입니다.")
        return self

    def resolve_dataframe(self, context: Optional[Any] = None) -> pd.DataFrame:
        """직접 전달된 데이터에서 DataFrame 생성.

        Args:
            context: 사용되지 않음 (인터페이스 일관성 유지용)

        Returns:
            pd.DataFrame
        """
        if isinstance(self.data, pd.DataFrame):
            df = self.data
        elif isinstance(self.data, list):
            df = pd.DataFrame(self.data)
        elif isinstance(self.data, dict):
            # dict of lists 또는 단일 레코드
            if all(isinstance(v, list) for v in self.data.values()):
                df = pd.DataFrame(self.data)
            else:
                df = pd.DataFrame([self.data])
        else:
            raise ValueError(
                f"DirectSource.data는 list, dict, DataFrame 중 하나여야 합니다. "
                f"받은 타입: {type(self.data).__name__}"
            )

        return self.select_columns(df)


# =============================================================================
# Union Type (Discriminated Union)
# =============================================================================

DataSource = Union[ArtifactSource, FileSource, DirectSource]
"""데이터 소스 유니온 타입.

source_type 필드로 구분된다:
- "artifact": ArtifactSource
- "file": FileSource
- "direct": DirectSource
"""


# =============================================================================
# Helper Functions
# =============================================================================

# 한국어 CSV 파일에서 자주 사용되는 인코딩 목록 (우선순위 순)
_ENCODINGS = ["utf-8", "cp949", "euc-kr", "utf-8-sig", "latin1"]


def _read_csv_with_encoding(path: str) -> pd.DataFrame:
    """여러 인코딩을 시도하여 CSV 파일을 읽습니다."""
    last_error: Exception | None = None
    for enc in _ENCODINGS:
        try:
            return pd.read_csv(path, encoding=enc)
        except (UnicodeDecodeError, UnicodeError) as e:
            last_error = e
            continue
    # 모든 인코딩 실패 시 마지막 에러 raise
    raise last_error or ValueError(f"Cannot decode CSV: {path}")


def _read_data_file(path: str) -> pd.DataFrame:
    """파일 경로에서 DataFrame 로드.

    지원 형식: CSV, JSON, Excel (.xlsx, .xls)
    """
    lower = path.lower()

    if lower.endswith(".csv"):
        return _read_csv_with_encoding(path)

    if lower.endswith(".json"):
        with open(path, "r", encoding="utf-8") as f:
            obj = json.load(f)
        if isinstance(obj, list):
            return pd.DataFrame(obj)
        elif isinstance(obj, dict):
            # Plotly JSON이나 메타데이터 포함 형식 처리
            if "data" in obj and isinstance(obj["data"], list):
                return pd.DataFrame(obj["data"])
            return pd.DataFrame([obj])
        raise ValueError(f"JSON 파일 형식이 올바르지 않습니다: {path}")

    if lower.endswith((".xlsx", ".xls")):
        return pd.read_excel(path)

    if lower.endswith(".parquet"):
        return pd.read_parquet(path)

    raise ValueError(f"지원하지 않는 파일 형식입니다: {path}")


def parse_data_source(raw_args: Dict[str, Any]) -> DataSource:
    """raw_args에서 적절한 DataSource 객체를 생성.

    Args:
        raw_args: 툴 입력 딕셔너리.
            - source_type이 있으면 새로운 형식으로 처리
            - kind가 있으면 기존 형식(하위 호환)으로 처리

    Returns:
        DataSource: 파싱된 데이터 소스 객체

    Raises:
        ValueError: 알 수 없는 소스 타입
    """
    # 새로운 형식: source_type 기반
    source_type = raw_args.get("source_type")

    if source_type == "artifact":
        return ArtifactSource.model_validate(raw_args)

    if source_type == "file":
        return FileSource.model_validate(raw_args)

    if source_type == "direct":
        return DirectSource.model_validate(raw_args)

    # 하위 호환: 기존 kind 기반 형식
    kind = raw_args.get("kind")

    if kind == "direct":
        return DirectSource(
            source_type="direct",
            data=raw_args.get("data"),
            columns=raw_args.get("columns"),
        )

    if kind == "locator":
        locator = raw_args.get("artifact_locator", {})
        return ArtifactSource(
            source_type="artifact",
            artifact_name=locator.get("artifact_name"),
            session_id=locator.get("session_id"),
            version=locator.get("version"),
            file_name=locator.get("file_name"),
            columns=raw_args.get("columns"),
        )

    # data가 직접 있으면 direct로 처리
    if "data" in raw_args:
        return DirectSource(
            source_type="direct",
            data=raw_args.get("data"),
            columns=raw_args.get("columns"),
        )

    raise ValueError(
        "source_type 또는 kind를 지정해야 합니다. "
        "지원: source_type='artifact'|'file'|'direct' 또는 kind='direct'|'locator'"
    )


def resolve_dataframe_from_args(
    raw_args: Dict[str, Any],
    context: Optional[Any] = None,
) -> tuple[pd.DataFrame, Optional[List[str]]]:
    """raw_args를 파싱하여 DataFrame과 columns 반환.

    기존 resolve_input_to_dataframe()의 확장 버전.

    Args:
        raw_args: 툴 입력 딕셔너리
        context: 툴 컨텍스트 (아티팩트 로드 시 필요)

    Returns:
        (DataFrame, columns): columns는 사용자가 지정한 컬럼 리스트
    """
    source = parse_data_source(raw_args)
    df = source.resolve_dataframe(context)
    return df, source.columns
