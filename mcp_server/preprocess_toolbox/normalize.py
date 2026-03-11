from __future__ import annotations

from typing import Any, Dict, Optional, Tuple, List

import numpy as np
import pandas as pd

from ..utils.plot_io import safe_run_tool


def normalize(args: Dict[str, Any]) -> Dict[str, Any]:
    """수치형 컬럼을 정규화(Normalization)하여 새로운 데이터셋을 생성한다.

    다양한 정규화/스케일링 방법을 지원한다:
    - min_max: 0~1 범위로 스케일링 (Min-Max Normalization)
    - z_score: 평균 0, 표준편차 1로 표준화 (Z-Score Standardization)
    - robust: 중앙값과 IQR 기반 스케일링 (이상치에 강건)
    - log: 로그 변환 (양수 값만)
    - max_abs: 최대 절댓값으로 나누어 -1~1 범위

    데이터 입력 방식 (source_type으로 구분):
      1. artifact (권장) - ADK 아티팩트에서 로드:
         {
           "source_type": "artifact",
           "artifact_name": "features",
           "columns": ["price", "age"],
           "method": "z_score"
         }

      2. file - 로컬 파일에서 로드:
         {
           "source_type": "file",
           "path": "C:/data/features.csv",
           "columns": ["price", "age"],
           "method": "min_max"
         }

      3. direct - 데이터 직접 전달:
         {
           "source_type": "direct",
           "data": [{"a":10,"b":100}, {"a":20,"b":200}],
           "columns": ["a", "b"],
           "method": "min_max"
         }

      하위 호환 (기존 형식):
        - kind="direct" + data=[...]
        - kind="locator" + artifact_locator={...}

    처리 파라미터:
      - columns (list[str], optional): 정규화할 컬럼들. 없으면 모든 수치형 컬럼
      - method (str, default="min_max"): 정규화 방법
        - "min_max": (x - min) / (max - min) → 0~1 범위
        - "z_score": (x - mean) / std → 평균 0, 표준편차 1
        - "robust": (x - median) / IQR → 이상치에 강건
        - "log": log(x + 1) → 로그 변환 (양의 왜도 완화)
        - "log10": log10(x + 1) → 10진 로그 변환
        - "max_abs": x / max(|x|) → -1~1 범위
      - suffix (str, default="_norm"): 정규화된 컬럼에 붙일 접미사. 빈 문자열이면 원본 덮어쓰기

    출력:
      {
        "status": "success",
        "outputs": [{"type": "resource_link", "uri": "mcp://resource/xxx.csv", ...}]
      }
    """

    def _get_numeric_columns(df: pd.DataFrame, columns: Optional[List[str]]) -> List[str]:
        """수치형 컬럼만 필터링."""
        if columns:
            candidates = [c for c in columns if c in df.columns]
        else:
            candidates = df.columns.tolist()

        return [c for c in candidates if pd.api.types.is_numeric_dtype(df[c])]

    def _min_max(series: pd.Series) -> pd.Series:
        """Min-Max 정규화."""
        min_val = series.min()
        max_val = series.max()
        if max_val - min_val == 0:
            return pd.Series(0.0, index=series.index)
        return (series - min_val) / (max_val - min_val)

    def _z_score(series: pd.Series) -> pd.Series:
        """Z-Score 표준화."""
        mean = series.mean()
        std = series.std()
        if std == 0:
            return pd.Series(0.0, index=series.index)
        return (series - mean) / std

    def _robust(series: pd.Series) -> pd.Series:
        """Robust 스케일링 (중앙값, IQR 기반)."""
        median = series.median()
        q1 = series.quantile(0.25)
        q3 = series.quantile(0.75)
        iqr = q3 - q1
        if iqr == 0:
            return pd.Series(0.0, index=series.index)
        return (series - median) / iqr

    def _log_transform(series: pd.Series) -> pd.Series:
        """자연로그 변환."""
        # 음수 값 처리: 최소값을 양수로 shift
        min_val = series.min()
        if min_val <= 0:
            shifted = series - min_val + 1
        else:
            shifted = series + 1
        return np.log(shifted)

    def _log10_transform(series: pd.Series) -> pd.Series:
        """10진 로그 변환."""
        min_val = series.min()
        if min_val <= 0:
            shifted = series - min_val + 1
        else:
            shifted = series + 1
        return np.log10(shifted)

    def _max_abs(series: pd.Series) -> pd.Series:
        """Max Absolute 스케일링."""
        max_abs = series.abs().max()
        if max_abs == 0:
            return pd.Series(0.0, index=series.index)
        return series / max_abs

    def core_fn(df: pd.DataFrame, columns: Optional[list], raw_args: Dict[str, Any]) -> Tuple[pd.DataFrame, Dict[str, Any]]:
        if df is None or df.empty:
            raise ValueError("입력 데이터가 비어있습니다.")

        method = (raw_args.get("method") or "min_max").strip().lower()
        suffix = raw_args.get("suffix", "_norm")
        if suffix is None:
            suffix = "_norm"

        target_cols = _get_numeric_columns(df, columns)

        if not target_cols:
            raise ValueError("정규화할 수치형 컬럼이 없습니다.")

        # 정규화 함수 매핑
        normalize_funcs = {
            "min_max": _min_max,
            "z_score": _z_score,
            "robust": _robust,
            "log": _log_transform,
            "log10": _log10_transform,
            "max_abs": _max_abs,
        }

        if method not in normalize_funcs:
            raise ValueError(f"지원하지 않는 method입니다: {method}. "
                           "min_max|z_score|robust|log|log10|max_abs 중 선택하세요.")

        func = normalize_funcs[method]
        result_df = df.copy()

        stats = {}
        for col in target_cols:
            original = result_df[col].copy()
            normalized = func(original)

            if suffix:
                new_col = f"{col}{suffix}"
                result_df[new_col] = normalized
            else:
                result_df[col] = normalized

            # 통계 정보 저장
            stats[col] = {
                "original_min": float(original.min()) if not original.isna().all() else None,
                "original_max": float(original.max()) if not original.isna().all() else None,
                "original_mean": float(original.mean()) if not original.isna().all() else None,
                "original_std": float(original.std()) if not original.isna().all() else None,
                "normalized_min": float(normalized.min()) if not normalized.isna().all() else None,
                "normalized_max": float(normalized.max()) if not normalized.isna().all() else None,
            }

        meta = {
            "method": method,
            "target_columns": target_cols,
            "suffix": suffix,
            "overwrite": suffix == "",
            "n_columns_normalized": len(target_cols),
            "column_stats": stats,
            "rows": int(len(result_df)),
            "cols": int(len(result_df.columns)),
        }

        return result_df, meta

    def description_builder(_df: pd.DataFrame, _result_obj: Any, meta: Dict[str, Any]) -> str:
        parts = []

        method_names = {
            "min_max": "Min-Max (0~1 범위)",
            "z_score": "Z-Score (평균 0, 표준편차 1)",
            "robust": "Robust (중앙값/IQR 기반)",
            "log": "자연로그 변환",
            "log10": "10진 로그 변환",
            "max_abs": "Max Absolute (-1~1 범위)",
        }
        method = meta.get("method", "")
        method_desc = method_names.get(method, method)

        parts.append(f"{method_desc} 정규화를 수행했습니다.")
        parts.append(f"정규화된 컬럼: {meta['n_columns_normalized']}개")

        if meta.get("overwrite"):
            parts.append("(원본 컬럼 덮어쓰기)")
        else:
            parts.append(f"(접미사: {meta['suffix']})")

        parts.append(f"결과: {meta['rows']}행 × {meta['cols']}열")

        return " ".join(parts)

    return safe_run_tool(
        raw_args=args,
        core_fn=core_fn,
        title="normalize",
        ext="csv",
        description_builder=description_builder,
    )
