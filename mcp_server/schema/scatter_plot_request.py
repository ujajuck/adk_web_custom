"""산점도 Request 스키마.

산점도는 두 수치형 변수의 관계를 점으로 시각화합니다.
"""
from __future__ import annotations

from typing import Any, Dict, List, Literal, Optional, Union

import pandas as pd
from pydantic import BaseModel, ConfigDict, Field

from .base_source import ArtifactSource, FileSource, TabularDirectSource


# 산점도용 소스 타입 (테이블 형식 데이터)
ScatterPlotSource = Union[ArtifactSource, FileSource, TabularDirectSource]


class ScatterPlotRequest(BaseModel):
    """산점도 요청 스키마.

    Example (직접 데이터):
        {
            "source": {"source_type": "direct", "data": [{"x": 1, "y": 2}]},
            "x": "x",
            "y": "y",
            "trendline": true
        }

    Example (아티팩트):
        {
            "source": {
                "source_type": "artifact",
                "artifact_name": "data.csv"
            },
            "x": "age",
            "y": "income",
            "color": "gender",
            "trendline": true
        }
    """
    model_config = ConfigDict(extra="ignore")

    # 데이터 소스
    source: ScatterPlotSource = Field(..., discriminator="source_type")

    # 축 지정 (필수)
    x: Optional[str] = Field(None, description="x축 컬럼명 (수치형)")
    y: Optional[str] = Field(None, description="y축 컬럼명 (수치형)")
    columns: Optional[List[str]] = Field(None, description="[x, y] 형태로 지정 가능")

    # 시각적 옵션
    color: Optional[str] = Field(None, description="점 색상 구분 컬럼 (범주형)")
    size: Optional[str] = Field(None, description="점 크기 컬럼 (수치형)")
    opacity: float = Field(0.7, description="점 투명도", ge=0, le=1)

    # 분석 옵션
    trendline: bool = Field(False, description="회귀 추세선 표시")
    max_points: int = Field(5000, description="최대 표시 점 개수", ge=1)

    # 공통 옵션
    title: Optional[str] = Field(None, description="그래프 제목")

    def resolve_dataframe(self) -> pd.DataFrame:
        """소스에서 DataFrame 로드."""
        return self.source.resolve_dataframe()

    def get_x_column(self, df: pd.DataFrame) -> Optional[str]:
        """x축 컬럼 결정."""
        if self.x and self.x in df.columns:
            return self.x
        if self.columns and len(self.columns) > 0 and self.columns[0] in df.columns:
            return self.columns[0]
        return None

    def get_y_column(self, df: pd.DataFrame) -> Optional[str]:
        """y축 컬럼 결정."""
        if self.y and self.y in df.columns:
            return self.y
        if self.columns and len(self.columns) > 1 and self.columns[1] in df.columns:
            return self.columns[1]
        return None
