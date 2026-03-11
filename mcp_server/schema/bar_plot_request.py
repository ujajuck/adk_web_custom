"""막대 그래프 Request 스키마.

막대 그래프는 범주별 값(빈도 또는 집계)을 시각화합니다.
"""
from __future__ import annotations

from typing import Any, Dict, List, Literal, Optional, Union

import pandas as pd
from pydantic import BaseModel, ConfigDict, Field

from .base_source import ArtifactSource, FileSource, TabularDirectSource


# 막대그래프용 소스 타입 (테이블 형식 데이터)
BarPlotSource = Union[ArtifactSource, FileSource, TabularDirectSource]


class BarPlotRequest(BaseModel):
    """막대 그래프 요청 스키마.

    Example (직접 데이터):
        {
            "source": {"source_type": "direct", "data": [{"cat": "A", "val": 10}]},
            "x": "cat",
            "y": "val",
            "agg": "sum"
        }

    Example (아티팩트):
        {
            "source": {
                "source_type": "artifact",
                "artifact_name": "sales.csv"
            },
            "x": "category",
            "y": "amount",
            "sort": "desc",
            "top_k": 10
        }
    """
    model_config = ConfigDict(extra="ignore")

    # 데이터 소스
    source: BarPlotSource = Field(..., discriminator="source_type")

    # 축 지정
    x: Optional[str] = Field(None, description="x축(범주) 컬럼명")
    y: Optional[str] = Field(None, description="y축(수치) 컬럼명. 없으면 빈도(count)")
    columns: Optional[List[str]] = Field(None, description="[x, y] 형태로 지정 가능")

    # 집계 옵션
    agg: Literal["sum", "mean", "count", "median", "max", "min"] = Field(
        "sum", description="y 집계 방식"
    )

    # 표시 옵션
    top_k: int = Field(30, description="상위 N개 막대만 표시", ge=1)
    sort: Literal["desc", "asc", "none"] = Field("desc", description="정렬 방식")
    null_label: str = Field("null", description="결측값 라벨")

    # 공통 옵션
    title: Optional[str] = Field(None, description="그래프 제목")

    def resolve_dataframe(self) -> pd.DataFrame:
        """소스에서 DataFrame 로드."""
        return self.source.resolve_dataframe()

    def get_x_column(self, df: pd.DataFrame) -> str:
        """x축 컬럼 결정."""
        if self.x and self.x in df.columns:
            return self.x
        if self.columns and len(self.columns) > 0 and self.columns[0] in df.columns:
            return self.columns[0]
        return df.columns[0]

    def get_y_column(self, df: pd.DataFrame) -> Optional[str]:
        """y축 컬럼 결정. None이면 빈도 모드."""
        if self.y and self.y in df.columns:
            return self.y
        if self.columns and len(self.columns) > 1 and self.columns[1] in df.columns:
            return self.columns[1]
        return None
