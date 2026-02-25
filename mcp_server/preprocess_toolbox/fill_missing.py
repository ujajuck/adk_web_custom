from __future__ import annotations

from typing import Any, Dict, Optional, Tuple, List

import numpy as np
import pandas as pd

from ..utils.plot_io import safe_run_tool, make_job_id
from ..utils.path_resolver import save_resource


def fill_missing(args: Dict[str, Any]) -> Dict[str, Any]:
    """결측치(Missing Values)를 처리하여 새로운 데이터셋을 생성한다.

    다양한 결측치 처리 방법을 지원한다:
    - 삭제: 결측치가 있는 행 또는 열 삭제
    - 대체: 평균, 중앙값, 최빈값, 특정 값으로 대체
    - 보간: 선형 보간, 앞/뒤 값으로 채우기

    입력 예시:
      - direct:
        {"kind":"direct","data":[{"a":1,"b":null},{"a":2,"b":3}],"columns":["b"],"method":"mean"}
      - locator(LLM이 채우는 필드: artifact_name/file_name):
        {"kind":"locator","artifact_locator":{"artifact_name":"sales","file_name":"sales.csv"},"columns":["price","quantity"],"method":"median"}

    파라미터:
      - columns (list[str], optional): 처리할 컬럼들. 없으면 전체 컬럼 대상
      - method (str, default="mean"): 결측치 처리 방법
        - "drop_rows": 결측치가 있는 행 삭제
        - "drop_cols": 결측 비율이 threshold 이상인 열 삭제
        - "mean": 평균으로 대체 (수치형)
        - "median": 중앙값으로 대체 (수치형)
        - "mode": 최빈값으로 대체 (범주형/수치형)
        - "constant": fill_value로 대체
        - "ffill": 앞의 값으로 채우기 (시계열)
        - "bfill": 뒤의 값으로 채우기 (시계열)
        - "interpolate": 선형 보간 (수치형)
      - fill_value (any, optional): method="constant"일 때 사용할 값
      - threshold (float, default=0.5): method="drop_cols"일 때 삭제 기준 비율
      - subset (list[str], optional): method="drop_rows"일 때 검사할 컬럼 한정

    출력:
      {
        "status": "success",
        "outputs": [{"type": "resource_link", "uri": "mcp://resource/xxx.csv", ...}]
      }
    """

    def _get_target_columns(df: pd.DataFrame, columns: Optional[List[str]]) -> List[str]:
        """처리 대상 컬럼 결정."""
        if columns:
            return [c for c in columns if c in df.columns]
        return df.columns.tolist()

    def _fill_mean(df: pd.DataFrame, cols: List[str]) -> pd.DataFrame:
        """수치형 컬럼을 평균으로 대체."""
        for col in cols:
            if pd.api.types.is_numeric_dtype(df[col]):
                df[col] = df[col].fillna(df[col].mean())
        return df

    def _fill_median(df: pd.DataFrame, cols: List[str]) -> pd.DataFrame:
        """수치형 컬럼을 중앙값으로 대체."""
        for col in cols:
            if pd.api.types.is_numeric_dtype(df[col]):
                df[col] = df[col].fillna(df[col].median())
        return df

    def _fill_mode(df: pd.DataFrame, cols: List[str]) -> pd.DataFrame:
        """최빈값으로 대체."""
        for col in cols:
            mode_val = df[col].mode()
            if len(mode_val) > 0:
                df[col] = df[col].fillna(mode_val.iloc[0])
        return df

    def _fill_constant(df: pd.DataFrame, cols: List[str], value: Any) -> pd.DataFrame:
        """특정 값으로 대체."""
        for col in cols:
            df[col] = df[col].fillna(value)
        return df

    def _fill_ffill(df: pd.DataFrame, cols: List[str]) -> pd.DataFrame:
        """앞의 값으로 채우기."""
        for col in cols:
            df[col] = df[col].ffill()
        return df

    def _fill_bfill(df: pd.DataFrame, cols: List[str]) -> pd.DataFrame:
        """뒤의 값으로 채우기."""
        for col in cols:
            df[col] = df[col].bfill()
        return df

    def _interpolate(df: pd.DataFrame, cols: List[str]) -> pd.DataFrame:
        """선형 보간."""
        for col in cols:
            if pd.api.types.is_numeric_dtype(df[col]):
                df[col] = df[col].interpolate(method="linear")
        return df

    def core_fn(df: pd.DataFrame, columns: Optional[list], raw_args: Dict[str, Any]) -> Tuple[pd.DataFrame, Dict[str, Any]]:
        if df is None or df.empty:
            raise ValueError("입력 데이터가 비어있습니다.")

        method = (raw_args.get("method") or "mean").strip().lower()
        fill_value = raw_args.get("fill_value")
        threshold = float(raw_args.get("threshold", 0.5))
        subset = raw_args.get("subset")

        # 처리 전 결측치 통계
        n_rows_before = len(df)
        n_cols_before = len(df.columns)
        missing_before = int(df.isna().sum().sum())

        target_cols = _get_target_columns(df, columns)
        result_df = df.copy()

        if method == "drop_rows":
            check_cols = subset if subset else target_cols
            check_cols = [c for c in check_cols if c in result_df.columns]
            result_df = result_df.dropna(subset=check_cols)

        elif method == "drop_cols":
            na_ratio = result_df[target_cols].isna().mean()
            drop_cols = na_ratio[na_ratio >= threshold].index.tolist()
            result_df = result_df.drop(columns=drop_cols, errors="ignore")

        elif method == "mean":
            result_df = _fill_mean(result_df, target_cols)

        elif method == "median":
            result_df = _fill_median(result_df, target_cols)

        elif method == "mode":
            result_df = _fill_mode(result_df, target_cols)

        elif method == "constant":
            if fill_value is None:
                raise ValueError("method='constant'일 때 fill_value를 지정해주세요.")
            result_df = _fill_constant(result_df, target_cols, fill_value)

        elif method == "ffill":
            result_df = _fill_ffill(result_df, target_cols)

        elif method == "bfill":
            result_df = _fill_bfill(result_df, target_cols)

        elif method == "interpolate":
            result_df = _interpolate(result_df, target_cols)

        else:
            raise ValueError(f"지원하지 않는 method입니다: {method}. "
                           "drop_rows|drop_cols|mean|median|mode|constant|ffill|bfill|interpolate 중 선택하세요.")

        # 처리 후 통계
        n_rows_after = len(result_df)
        n_cols_after = len(result_df.columns)
        missing_after = int(result_df.isna().sum().sum())

        meta = {
            "method": method,
            "target_columns": target_cols,
            "fill_value": fill_value if method == "constant" else None,
            "threshold": threshold if method == "drop_cols" else None,
            "rows_before": n_rows_before,
            "rows_after": n_rows_after,
            "rows_removed": n_rows_before - n_rows_after,
            "cols_before": n_cols_before,
            "cols_after": n_cols_after,
            "cols_removed": n_cols_before - n_cols_after,
            "missing_before": missing_before,
            "missing_after": missing_after,
            "missing_filled": missing_before - missing_after,
        }

        return result_df, meta

    def description_builder(_df: pd.DataFrame, _result_obj: Any, meta: Dict[str, Any]) -> str:
        parts = []
        method = meta.get("method", "")

        if method == "drop_rows":
            parts.append(f"결측치가 있는 행을 삭제했습니다.")
            parts.append(f"삭제된 행: {meta['rows_removed']}개")
        elif method == "drop_cols":
            parts.append(f"결측 비율 {meta['threshold']*100:.0f}% 이상인 열을 삭제했습니다.")
            parts.append(f"삭제된 열: {meta['cols_removed']}개")
        else:
            method_names = {
                "mean": "평균", "median": "중앙값", "mode": "최빈값",
                "constant": "지정값", "ffill": "앞의 값", "bfill": "뒤의 값",
                "interpolate": "선형 보간"
            }
            parts.append(f"결측치를 {method_names.get(method, method)}(으)로 대체했습니다.")

        parts.append(f"처리 전 결측: {meta['missing_before']}개 → 처리 후: {meta['missing_after']}개")
        parts.append(f"최종 데이터: {meta['rows_after']}행 × {meta['cols_after']}열")

        return " ".join(parts)

    return safe_run_tool(
        raw_args=args,
        core_fn=core_fn,
        title="fill_missing",
        ext="csv",
        description_builder=description_builder,
    )
