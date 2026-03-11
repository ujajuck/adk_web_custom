from __future__ import annotations

from typing import Any, Dict, Optional, Tuple, List

import numpy as np
import pandas as pd

from ..utils.plot_io import safe_run_tool


def remove_outliers(args: Dict[str, Any]) -> Dict[str, Any]:
    """이상치(Outliers)를 탐지하고 제거하여 새로운 데이터셋을 생성한다.

    다양한 이상치 탐지 방법을 지원한다:
    - IQR: 사분위수 범위 기반 (Q1 - k*IQR, Q3 + k*IQR)
    - Z-score: 표준편차 기반 (|z| > threshold)
    - Percentile: 백분위수 기반 (상하위 p% 제거)

    데이터 입력 방식 (source_type으로 구분):
      1. artifact (권장) - ADK 아티팩트에서 로드:
         {
           "source_type": "artifact",
           "artifact_name": "sales_data",
           "columns": ["price", "quantity"],
           "method": "iqr"
         }

      2. file - 로컬 파일에서 로드:
         {
           "source_type": "file",
           "path": "C:/data/sales.csv",
           "columns": ["price"],
           "method": "zscore",
           "threshold": 3
         }

      3. direct - 데이터 직접 전달:
         {
           "source_type": "direct",
           "data": [{"a":1,"b":100}, {"a":2,"b":3}],
           "columns": ["b"],
           "method": "iqr"
         }

    처리 파라미터:
      - columns (list[str], optional): 이상치를 탐지할 컬럼들. 없으면 전체 수치형 컬럼
      - method (str, default="iqr"): 이상치 탐지 방법
        - "iqr": IQR 기반 (기본값, k=1.5)
        - "zscore": Z-score 기반 (threshold=3)
        - "percentile": 백분위수 기반
      - k (float, default=1.5): IQR 방법의 계수
      - threshold (float, default=3.0): Z-score 방법의 임계값
      - lower_pct (float, default=1): 백분위수 방법의 하위 퍼센트
      - upper_pct (float, default=99): 백분위수 방법의 상위 퍼센트
      - action (str, default="remove"): 이상치 처리 방식
        - "remove": 이상치 행 삭제
        - "cap": 경계값으로 대체
        - "nan": NaN으로 대체

    출력:
      {
        "status": "success",
        "outputs": [{"type": "resource_link", "uri": "mcp://resource/xxx.csv", ...}]
      }
    """

    def _detect_iqr(data: pd.Series, k: float) -> Tuple[float, float]:
        """IQR 기반 이상치 경계 계산."""
        q1 = data.quantile(0.25)
        q3 = data.quantile(0.75)
        iqr = q3 - q1
        lower = q1 - k * iqr
        upper = q3 + k * iqr
        return lower, upper

    def _detect_zscore(data: pd.Series, threshold: float) -> Tuple[float, float]:
        """Z-score 기반 이상치 경계 계산."""
        mean = data.mean()
        std = data.std()
        lower = mean - threshold * std
        upper = mean + threshold * std
        return lower, upper

    def _detect_percentile(data: pd.Series, lower_pct: float, upper_pct: float) -> Tuple[float, float]:
        """백분위수 기반 이상치 경계 계산."""
        lower = data.quantile(lower_pct / 100)
        upper = data.quantile(upper_pct / 100)
        return lower, upper

    def core_fn(df: pd.DataFrame, columns: Optional[list], raw_args: Dict[str, Any]) -> Tuple[pd.DataFrame, Dict[str, Any]]:
        if df is None or df.empty:
            raise ValueError("입력 데이터가 비어있습니다.")

        method = (raw_args.get("method") or "iqr").strip().lower()
        k = float(raw_args.get("k", 1.5))
        threshold = float(raw_args.get("threshold", 3.0))
        lower_pct = float(raw_args.get("lower_pct", 1))
        upper_pct = float(raw_args.get("upper_pct", 99))
        action = (raw_args.get("action") or "remove").strip().lower()

        # 처리 전 통계
        n_rows_before = len(df)

        # 수치형 컬럼만 대상
        numeric_cols = df.select_dtypes(include=[np.number]).columns.tolist()
        target_cols = [c for c in (columns or numeric_cols) if c in numeric_cols]

        if not target_cols:
            raise ValueError("이상치를 탐지할 수치형 컬럼이 없습니다.")

        result_df = df.copy()
        outlier_info = {}

        for col in target_cols:
            data = result_df[col].dropna()
            if len(data) == 0:
                continue

            # 경계 계산
            if method == "iqr":
                lower, upper = _detect_iqr(data, k)
            elif method == "zscore":
                lower, upper = _detect_zscore(data, threshold)
            elif method == "percentile":
                lower, upper = _detect_percentile(data, lower_pct, upper_pct)
            else:
                raise ValueError(f"지원하지 않는 method: {method}. iqr|zscore|percentile 중 선택하세요.")

            # 이상치 마스크
            outlier_mask = (result_df[col] < lower) | (result_df[col] > upper)
            n_outliers = outlier_mask.sum()

            outlier_info[col] = {
                "n_outliers": int(n_outliers),
                "pct_outliers": float(n_outliers / len(df) * 100),
                "lower_bound": float(lower),
                "upper_bound": float(upper),
            }

            # 이상치 처리
            if action == "remove":
                result_df = result_df[~outlier_mask]
            elif action == "cap":
                result_df.loc[result_df[col] < lower, col] = lower
                result_df.loc[result_df[col] > upper, col] = upper
            elif action == "nan":
                result_df.loc[outlier_mask, col] = np.nan
            else:
                raise ValueError(f"지원하지 않는 action: {action}. remove|cap|nan 중 선택하세요.")

        n_rows_after = len(result_df)
        total_outliers = sum(info["n_outliers"] for info in outlier_info.values())

        meta = {
            "method": method,
            "action": action,
            "target_columns": target_cols,
            "rows_before": n_rows_before,
            "rows_after": n_rows_after,
            "rows_removed": n_rows_before - n_rows_after,
            "total_outliers_detected": total_outliers,
            "outlier_info": outlier_info,
        }

        return result_df, meta

    def description_builder(_df: pd.DataFrame, _result_obj: Any, meta: Dict[str, Any]) -> str:
        parts = []
        method_names = {"iqr": "IQR", "zscore": "Z-score", "percentile": "백분위수"}
        action_names = {"remove": "삭제", "cap": "경계값으로 대체", "nan": "NaN으로 대체"}

        parts.append(f"{method_names.get(meta['method'], meta['method'])} 방법으로 이상치를 탐지했습니다.")
        parts.append(f"총 {meta['total_outliers_detected']}개의 이상치를 {action_names.get(meta['action'], meta['action'])}했습니다.")

        if meta["action"] == "remove":
            parts.append(f"삭제된 행: {meta['rows_removed']}개")

        parts.append(f"최종 데이터: {meta['rows_after']}행")

        return " ".join(parts)

    return safe_run_tool(
        raw_args=args,
        core_fn=core_fn,
        title="remove_outliers",
        ext="csv",
        description_builder=description_builder,
    )
