"""히스토그램 Request 스키마.

히스토그램은 단일 컬럼의 분포를 시각화합니다.
수치형 데이터는 구간(bins)으로, 범주형 데이터는 빈도로 표시됩니다.
"""
from __future__ import annotations

from typing import Any, Dict, List, Literal, Optional, Union

import pandas as pd
from pydantic import BaseModel, ConfigDict, Field

from .base_source import ArtifactSource, FileSource, TabularDirectSource


# 히스토그램용 소스 타입 (테이블 형식 데이터)
HistogramSource = Union[ArtifactSource, FileSource, TabularDirectSource]


class HistogramRequest(BaseModel):
    """히스토그램 요청 스키마.

    Example (직접 데이터):
        {
            "source": {"source_type": "direct", "data": [{"age": 25}, {"age": 30}]},
            "column": "age",
            "bins": 20
        }

    Example (아티팩트):
        {
            "source": {
                "source_type": "artifact",
                "artifact_name": "pokemon.csv",
                "columns": ["weight_kg"]
            },
            "column": "weight_kg",
            "bins": 30
        }
    """
    model_config = ConfigDict(extra="ignore")

    # 데이터 소스
    source: HistogramSource = Field(..., discriminator="source_type")

    # 컬럼 지정
    column: Optional[str] = Field(None, description="히스토그램을 그릴 컬럼명")
    columns: Optional[List[str]] = Field(None, description="컬럼명 목록 (첫 번째 사용)")

    # 히스토그램 옵션 (수치형)
    bins: int = Field(30, description="구간 수", ge=1)
    density: bool = Field(False, description="밀도(비율)로 표시")
    log_y: bool = Field(False, description="y축 로그 스케일")
    range_min: Optional[float] = Field(None, description="x축 최소값")
    range_max: Optional[float] = Field(None, description="x축 최대값")

    # 히스토그램 옵션 (범주형)
    top_k: int = Field(30, description="상위 N개만 표시", ge=1)
    other_label: str = Field("(others)", description="나머지 항목 라벨")
    null_label: str = Field("null", description="결측값 라벨")

    # 공통 옵션
    title: Optional[str] = Field(None, description="그래프 제목")
    numeric_ratio_threshold: float = Field(0.6, description="수치형 판정 기준", ge=0, le=1)

    def resolve_dataframe(self) -> pd.DataFrame:
        """소스에서 DataFrame 로드."""
        return self.source.resolve_dataframe()

    def get_column(self, df: pd.DataFrame) -> str:
        """사용할 컬럼 결정."""
        if self.column and self.column in df.columns:
            return self.column
        if self.columns and len(self.columns) > 0 and self.columns[0] in df.columns:
            return self.columns[0]
        if "x" in df.columns:
            return "x"
        return df.columns[0]
