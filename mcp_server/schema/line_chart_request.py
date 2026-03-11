"""선 그래프 Request 스키마.

선 그래프는 시계열 데이터나 연속적인 변화를 시각화합니다.
여러 라인(시리즈)을 하나의 그래프에 표시할 수 있습니다.

LineChart는 Segment 기반 데이터 형식을 사용합니다:
- 각 Segment는 하나의 x축 기준에 여러 y 시리즈를 가질 수 있음
- x_mode로 여러 Segment를 병합하는 방식 지정
"""
from __future__ import annotations

from typing import Any, Dict, List, Literal, Optional, Sequence, Union

import pandas as pd
from pydantic import BaseModel, ConfigDict, Field

from ..utils.path_resolver import get_artifact_path


class LinePlotSegment(BaseModel):
    """라인 차트 데이터 세그먼트.

    하나의 x축 기준에 대해 여러 y 시리즈를 가집니다.
    """
    name: str = Field(..., description="세그먼트 이름")
    x: List[Any] = Field(..., description="x축 값 목록")
    y_series: Dict[str, List[float]] = Field(..., description="y 시리즈 {컬럼명: 값목록}")


class LineDirectSource(BaseModel):
    """라인 차트용 직접 데이터 소스.

    Segment 형식으로 데이터를 직접 전달합니다.
    """
    model_config = ConfigDict(extra="ignore")

    source_type: Literal["direct"] = "direct"
    segments: Sequence[LinePlotSegment] = Field(..., description="세그먼트 목록")

    def resolve_segments(self) -> Sequence[LinePlotSegment]:
        """세그먼트 반환."""
        return self.segments


class LineArtifactSource(BaseModel):
    """라인 차트용 아티팩트 소스.

    CSV 아티팩트를 읽어 Segment로 변환합니다.
    """
    model_config = ConfigDict(extra="ignore")

    source_type: Literal["artifact"] = "artifact"
    artifact_name: str = Field(..., description="아티팩트 파일명")
    user_id: Optional[str] = Field(None, description="사용자 ID (ADK callback이 자동 주입)")
    session_id: Optional[str] = Field(None, description="세션 ID (ADK callback이 자동 주입)")
    version: int = Field(0, description="아티팩트 버전")
    x_col: Optional[str] = Field(None, description="x축 컬럼명")
    y_cols: Optional[List[str]] = Field(None, description="y축 컬럼명 목록")

    def resolve_segments(self) -> Sequence[LinePlotSegment]:
        """아티팩트를 읽어 세그먼트로 변환."""
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
        return build_segments_from_df(df, x_col=self.x_col, y_cols=self.y_cols)


class LineFileSource(BaseModel):
    """라인 차트용 파일 소스."""
    model_config = ConfigDict(extra="ignore")

    source_type: Literal["file"] = "file"
    path: str = Field(..., description="파일 경로")
    x_col: Optional[str] = Field(None, description="x축 컬럼명")
    y_cols: Optional[List[str]] = Field(None, description="y축 컬럼명 목록")

    def resolve_segments(self) -> Sequence[LinePlotSegment]:
        """파일을 읽어 세그먼트로 변환."""
        df = pd.read_csv(self.path)
        return build_segments_from_df(df, x_col=self.x_col, y_cols=self.y_cols)


def build_segments_from_df(
    df: pd.DataFrame,
    *,
    x_col: Optional[str] = None,
    y_cols: Optional[Sequence[str]] = None,
) -> Sequence[LinePlotSegment]:
    """DataFrame을 LinePlotSegment로 변환."""
    if df is None or df.empty:
        raise ValueError("DataFrame이 비어 있습니다.")

    # x축 결정
    if x_col is None or str(x_col).strip() == "":
        x_values: List[Any] = df.index.tolist()
        x_name = "(index)"
    else:
        if x_col not in df.columns:
            raise ValueError(f"x_col='{x_col}' 컬럼이 DataFrame에 없습니다.")
        x_values = df[x_col].tolist()
        x_name = x_col

    # y축 결정
    if y_cols is None or len(y_cols) == 0:
        # 수치형 컬럼 자동 선택
        numeric_cols = df.select_dtypes(include=["number"]).columns.tolist()
        if x_col in numeric_cols:
            numeric_cols.remove(x_col)
        y_cols = numeric_cols[:5]  # 최대 5개

    if not y_cols:
        raise ValueError("y축 컬럼을 지정하거나 수치형 컬럼이 필요합니다.")

    # y 시리즈 생성
    y_series: Dict[str, List[float]] = {}
    for y in y_cols:
        if y in df.columns:
            y_series[y] = pd.to_numeric(df[y], errors="coerce").tolist()

    seg = LinePlotSegment(name=x_name, x=x_values, y_series=y_series)
    return [seg]


# 라인 차트 소스 타입
LineChartSource = Union[LineArtifactSource, LineFileSource, LineDirectSource]


class LineChartRequest(BaseModel):
    """선 그래프 요청 스키마.

    Example (직접 데이터):
        {
            "source": {
                "source_type": "direct",
                "segments": [{"name": "data", "x": [1,2,3], "y_series": {"sales": [10,20,30]}}]
            },
            "title": "Sales Trend"
        }

    Example (아티팩트):
        {
            "source": {
                "source_type": "artifact",
                "artifact_name": "timeseries.csv",
                "x_col": "date",
                "y_cols": ["sales", "revenue"]
            },
            "x_mode": "concat",
            "markers": true
        }
    """
    model_config = ConfigDict(extra="ignore")

    # 데이터 소스
    source: LineChartSource = Field(..., discriminator="source_type")

    # 레이아웃 옵션
    title: str = Field("Line Plot", description="그래프 제목")
    x_mode: Literal["concat", "align", "keep"] = Field(
        "concat", description="여러 세그먼트 병합 방식"
    )

    # 시각적 옵션
    markers: bool = Field(False, description="마커 표시")
    fill: Optional[Literal["none", "tozeroy", "tonexty"]] = Field(
        None, description="채우기 옵션"
    )
    add_boundaries: bool = Field(True, description="경계선 추가")
    hovermode: str = Field("x unified", description="호버 모드")

    def resolve_segments(self) -> Sequence[LinePlotSegment]:
        """소스에서 세그먼트 로드."""
        return self.source.resolve_segments()
