from __future__ import annotations

from typing import Any, Dict, Optional, Tuple, List

import numpy as np
import pandas as pd

from ..utils.plot_io import safe_run_tool


def scale_features(args: Dict[str, Any]) -> Dict[str, Any]:
    """수치형 피처들을 스케일링(정규화/표준화)한다.

    다양한 스케일링 방법을 지원한다:
    - standard: Z-score 표준화 (평균 0, 표준편차 1)
    - minmax: Min-Max 스케일링 (0~1 범위)
    - robust: Robust 스케일링 (중앙값과 IQR 기반)
    - maxabs: MaxAbs 스케일링 (-1~1 범위)
    - log: 로그 변환 (양수 데이터에만 적용)

    데이터 입력 방식 (source_type으로 구분):
      1. artifact (권장):
         {
           "source_type": "artifact",
           "artifact_name": "features.csv",
           "columns": ["price", "quantity"],
           "method": "standard"
         }

      2. file:
         {
           "source_type": "file",
           "path": "C:/data/features.csv",
           "method": "minmax"
         }

      3. direct:
         {
           "source_type": "direct",
           "data": [...],
           "columns": ["x1", "x2"],
           "method": "robust"
         }

    스케일링 파라미터:
      - columns (list[str], optional): 스케일링할 컬럼들. 없으면 전체 수치형 컬럼
      - method (str, default="standard"): 스케일링 방법
        - "standard": Z-score 표준화
        - "minmax": Min-Max 스케일링 (range 파라미터로 범위 지정 가능)
        - "robust": Robust 스케일링 (이상치에 덜 민감)
        - "maxabs": MaxAbs 스케일링
        - "log": 로그 변환 (log1p 사용)
      - range (tuple, default=(0,1)): minmax 방법의 출력 범위

    출력:
      {
        "status": "success",
        "outputs": [{"type": "resource_link", "uri": "mcp://resource/xxx.csv", ...}]
      }
    """

    def _standard_scale(data: pd.Series) -> pd.Series:
        """Z-score 표준화."""
        mean = data.mean()
        std = data.std()
        if std == 0:
            return data - mean
        return (data - mean) / std

    def _minmax_scale(data: pd.Series, feature_range: Tuple[float, float]) -> pd.Series:
        """Min-Max 스케일링."""
        min_val = data.min()
        max_val = data.max()
        if max_val == min_val:
            return pd.Series([feature_range[0]] * len(data), index=data.index)
        scaled = (data - min_val) / (max_val - min_val)
        return scaled * (feature_range[1] - feature_range[0]) + feature_range[0]

    def _robust_scale(data: pd.Series) -> pd.Series:
        """Robust 스케일링 (중앙값, IQR 기반)."""
        median = data.median()
        q1 = data.quantile(0.25)
        q3 = data.quantile(0.75)
        iqr = q3 - q1
        if iqr == 0:
            return data - median
        return (data - median) / iqr

    def _maxabs_scale(data: pd.Series) -> pd.Series:
        """MaxAbs 스케일링."""
        max_abs = data.abs().max()
        if max_abs == 0:
            return data
        return data / max_abs

    def _log_scale(data: pd.Series) -> pd.Series:
        """로그 변환 (log1p)."""
        # 음수 값 처리
        if (data < 0).any():
            min_val = data.min()
            shifted = data - min_val + 1
            return np.log1p(shifted)
        return np.log1p(data)

    def core_fn(df: pd.DataFrame, columns: Optional[list], raw_args: Dict[str, Any]) -> Tuple[pd.DataFrame, Dict[str, Any]]:
        if df is None or df.empty:
            raise ValueError("입력 데이터가 비어있습니다.")

        method = (raw_args.get("method") or "standard").strip().lower()
        feature_range = raw_args.get("range", (0, 1))

        if isinstance(feature_range, (list, tuple)) and len(feature_range) == 2:
            feature_range = (float(feature_range[0]), float(feature_range[1]))
        else:
            feature_range = (0.0, 1.0)

        # 수치형 컬럼만 대상
        numeric_cols = df.select_dtypes(include=[np.number]).columns.tolist()
        target_cols = [c for c in (columns or numeric_cols) if c in numeric_cols]

        if not target_cols:
            raise ValueError("스케일링할 수치형 컬럼이 없습니다.")

        result_df = df.copy()
        scaling_info = {}

        for col in target_cols:
            original_mean = float(result_df[col].mean())
            original_std = float(result_df[col].std())
            original_min = float(result_df[col].min())
            original_max = float(result_df[col].max())

            if method == "standard":
                result_df[col] = _standard_scale(result_df[col])
            elif method == "minmax":
                result_df[col] = _minmax_scale(result_df[col], feature_range)
            elif method == "robust":
                result_df[col] = _robust_scale(result_df[col])
            elif method == "maxabs":
                result_df[col] = _maxabs_scale(result_df[col])
            elif method == "log":
                result_df[col] = _log_scale(result_df[col])
            else:
                raise ValueError(f"지원하지 않는 method: {method}. standard|minmax|robust|maxabs|log 중 선택하세요.")

            scaled_mean = float(result_df[col].mean())
            scaled_std = float(result_df[col].std())
            scaled_min = float(result_df[col].min())
            scaled_max = float(result_df[col].max())

            scaling_info[col] = {
                "original": {"mean": original_mean, "std": original_std, "min": original_min, "max": original_max},
                "scaled": {"mean": scaled_mean, "std": scaled_std, "min": scaled_min, "max": scaled_max},
            }

        meta = {
            "method": method,
            "target_columns": target_cols,
            "feature_range": feature_range if method == "minmax" else None,
            "scaling_info": scaling_info,
        }

        return result_df, meta

    def description_builder(_df: pd.DataFrame, _result_obj: Any, meta: Dict[str, Any]) -> str:
        method_names = {
            "standard": "Z-score 표준화",
            "minmax": "Min-Max 스케일링",
            "robust": "Robust 스케일링",
            "maxabs": "MaxAbs 스케일링",
            "log": "로그 변환",
        }
        parts = []
        parts.append(f"{method_names.get(meta['method'], meta['method'])}을 수행했습니다.")
        parts.append(f"대상 컬럼: {', '.join(meta['target_columns'][:5])}")

        if len(meta['target_columns']) > 5:
            parts.append(f"(외 {len(meta['target_columns'])-5}개)")

        if meta["method"] == "minmax" and meta["feature_range"]:
            parts.append(f"출력 범위: {meta['feature_range']}")

        return " ".join(parts)

    return safe_run_tool(
        raw_args=args,
        core_fn=core_fn,
        title="scale_features",
        ext="csv",
        description_builder=description_builder,
    )
