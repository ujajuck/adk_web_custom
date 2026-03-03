"""파이 차트 Request 스키마.

파이 차트는 범주별 비율/구성을 시각화합니다.
도넛 차트도 지원합니다.
"""
from __future__ import annotations

from typing import Any, Dict, List, Literal, Optional, Union

import pandas as pd
from pydantic import BaseModel, ConfigDict, Field

from .base_source import ArtifactSource, FileSource, TabularDirectSource


# 파이차트용 소스 타입 (테이블 형식 데이터)
PieChartSource = Union[ArtifactSource, FileSource, TabularDirectSource]


class PieChartRequest(BaseModel):
    """파이 차트 요청 스키마.

    Example (직접 데이터):
        {
            "source": {"source_type": "direct", "data": [{"cat": "A", "val": 30}]},
            "labels": "cat",
            "values": "val"
        }

    Example (아티팩트):
        {
            "source": {
                "source_type": "artifact",
                "artifact_name": "market.csv"
            },
            "labels": "company",
            "values": "share",
            "donut": true,
            "top_k": 5
        }
    """
    model_config = ConfigDict(extra="ignore")

    # 데이터 소스
    source: PieChartSource = Field(..., discriminator="source_type")

    # 컬럼 지정
    labels: Optional[str] = Field(None, description="범주/라벨 컬럼명")
    values: Optional[str] = Field(None, description="값 컬럼명. 없으면 빈도(count)")
    columns: Optional[List[str]] = Field(None, description="[labels, values] 형태로 지정 가능")

    # 집계 옵션
    agg: Literal["sum", "mean", "count"] = Field("sum", description="values 집계 방식")
    top_k: int = Field(10, description="상위 N개 항목만 표시", ge=1)
    other_label: str = Field("기타", description="나머지 항목 라벨")
    null_label: str = Field("null", description="결측 범주 라벨")

    # 차트 스타일
    donut: bool = Field(False, description="도넛 차트 (중앙 구멍)")
    show_percent: bool = Field(True, description="퍼센트 표시")

    # 공통 옵션
    title: Optional[str] = Field(None, description="그래프 제목")

    def resolve_dataframe(self) -> pd.DataFrame:
        """소스에서 DataFrame 로드."""
        return self.source.resolve_dataframe()

    def get_labels_column(self, df: pd.DataFrame) -> str:
        """라벨 컬럼 결정."""
        if self.labels and self.labels in df.columns:
            return self.labels
        if self.columns and len(self.columns) > 0 and self.columns[0] in df.columns:
            return self.columns[0]
        # 첫 번째 문자열/범주형 컬럼 자동 선택
        for col in df.columns:
            if df[col].dtype == "object" or str(df[col].dtype).startswith("category"):
                return col
        return df.columns[0]

    def get_values_column(self, df: pd.DataFrame) -> Optional[str]:
        """값 컬럼 결정. None이면 빈도 모드."""
        if self.values and self.values in df.columns:
            return self.values
        if self.columns and len(self.columns) > 1 and self.columns[1] in df.columns:
            return self.columns[1]
        return None
