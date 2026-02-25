from __future__ import annotations

from typing import Any, Dict, Optional, Tuple, List

import numpy as np
import pandas as pd

from ..utils.plot_io import safe_run_tool


def encode_categorical(args: Dict[str, Any]) -> Dict[str, Any]:
    """범주형 컬럼을 인코딩하여 새로운 데이터셋을 생성한다.

    머신러닝 모델 입력에 적합한 형태로 범주형 변수를 변환한다.
    다양한 인코딩 방법을 지원한다.

    입력 예시:
      - direct:
        {"kind":"direct","data":[{"color":"red"},{"color":"blue"},{"color":"red"}],"columns":["color"],"method":"onehot"}
      - locator(LLM이 채우는 필드: artifact_name/file_name):
        {"kind":"locator","artifact_locator":{"artifact_name":"customers","file_name":"customers.csv"},"columns":["gender","region"],"method":"label"}

    파라미터:
      - columns (list[str], optional): 인코딩할 컬럼들. 없으면 모든 object/category 컬럼
      - method (str, default="onehot"): 인코딩 방법
        - "onehot": 원-핫 인코딩 (각 범주를 별도 이진 컬럼으로)
        - "label": 레이블 인코딩 (범주를 정수로 변환)
        - "ordinal": 순서형 인코딩 (지정된 순서대로 정수 할당)
        - "frequency": 빈도 인코딩 (범주를 빈도로 대체)
        - "target": 타겟 인코딩 (범주를 타겟 평균으로 대체, target 컬럼 필요)
      - drop_first (bool, default=False): onehot에서 첫 범주 컬럼 제외 (다중공선성 방지)
      - handle_unknown (str, default="error"): 알 수 없는 범주 처리 방법
        - "error": 에러 발생
        - "ignore": 무시 (NaN 또는 0)
      - order (dict, optional): ordinal 인코딩 시 범주 순서 {컬럼: [순서리스트]}
      - target (str, optional): target 인코딩 시 타겟 컬럼명
      - min_frequency (int, default=1): 이 빈도 미만의 범주는 "other"로 묶음
      - other_label (str, default="__other__"): 희귀 범주를 묶을 라벨

    출력:
      {
        "status": "success",
        "outputs": [{"type": "resource_link", "uri": "mcp://resource/xxx.csv", ...}]
      }
    """

    def _get_categorical_columns(df: pd.DataFrame, columns: Optional[List[str]]) -> List[str]:
        """범주형 컬럼 필터링."""
        if columns:
            candidates = [c for c in columns if c in df.columns]
        else:
            candidates = df.columns.tolist()

        result = []
        for c in candidates:
            dtype = df[c].dtype
            if dtype == "object" or str(dtype).startswith("category") or dtype == "string":
                result.append(c)
        return result

    def _onehot_encode(df: pd.DataFrame, cols: List[str], drop_first: bool, min_freq: int, other_label: str) -> pd.DataFrame:
        """원-핫 인코딩."""
        result = df.copy()

        for col in cols:
            # 희귀 범주 처리
            if min_freq > 1:
                vc = result[col].value_counts()
                rare = vc[vc < min_freq].index.tolist()
                result[col] = result[col].replace(rare, other_label)

            dummies = pd.get_dummies(result[col], prefix=col, drop_first=drop_first, dtype=int)
            result = pd.concat([result.drop(columns=[col]), dummies], axis=1)

        return result

    def _label_encode(df: pd.DataFrame, cols: List[str], min_freq: int, other_label: str) -> Tuple[pd.DataFrame, Dict]:
        """레이블 인코딩."""
        result = df.copy()
        mappings = {}

        for col in cols:
            # 희귀 범주 처리
            if min_freq > 1:
                vc = result[col].value_counts()
                rare = vc[vc < min_freq].index.tolist()
                result[col] = result[col].replace(rare, other_label)

            unique_vals = result[col].dropna().unique().tolist()
            mapping = {v: i for i, v in enumerate(unique_vals)}
            result[col] = result[col].map(mapping)
            mappings[col] = mapping

        return result, mappings

    def _ordinal_encode(df: pd.DataFrame, cols: List[str], order: Dict[str, List]) -> Tuple[pd.DataFrame, Dict]:
        """순서형 인코딩."""
        result = df.copy()
        mappings = {}

        for col in cols:
            if col in order:
                # 지정된 순서 사용
                order_list = order[col]
                mapping = {v: i for i, v in enumerate(order_list)}
            else:
                # 알파벳 순서
                unique_vals = sorted(result[col].dropna().unique().tolist())
                mapping = {v: i for i, v in enumerate(unique_vals)}

            result[col] = result[col].map(mapping)
            mappings[col] = mapping

        return result, mappings

    def _frequency_encode(df: pd.DataFrame, cols: List[str]) -> Tuple[pd.DataFrame, Dict]:
        """빈도 인코딩."""
        result = df.copy()
        mappings = {}

        for col in cols:
            freq = result[col].value_counts(normalize=True)
            result[col] = result[col].map(freq)
            mappings[col] = freq.to_dict()

        return result, mappings

    def _target_encode(df: pd.DataFrame, cols: List[str], target_col: str) -> Tuple[pd.DataFrame, Dict]:
        """타겟 인코딩 (평균)."""
        if target_col not in df.columns:
            raise ValueError(f"target 컬럼 '{target_col}'이 데이터에 없습니다.")

        result = df.copy()
        result[target_col] = pd.to_numeric(result[target_col], errors="coerce")
        mappings = {}

        global_mean = result[target_col].mean()

        for col in cols:
            target_mean = result.groupby(col)[target_col].mean()
            result[col] = result[col].map(target_mean).fillna(global_mean)
            mappings[col] = target_mean.to_dict()

        return result, mappings

    def core_fn(df: pd.DataFrame, columns: Optional[list], raw_args: Dict[str, Any]) -> Tuple[pd.DataFrame, Dict[str, Any]]:
        if df is None or df.empty:
            raise ValueError("입력 데이터가 비어있습니다.")

        method = (raw_args.get("method") or "onehot").strip().lower()
        drop_first = bool(raw_args.get("drop_first", False))
        order = raw_args.get("order") or {}
        target_col = raw_args.get("target")
        min_freq = int(raw_args.get("min_frequency", 1))
        other_label = str(raw_args.get("other_label", "__other__"))

        target_cols = _get_categorical_columns(df, columns)

        if not target_cols:
            raise ValueError("인코딩할 범주형 컬럼이 없습니다.")

        # 원본 통계
        n_cols_before = len(df.columns)
        unique_counts = {col: int(df[col].nunique()) for col in target_cols}

        mappings = {}

        if method == "onehot":
            result_df = _onehot_encode(df, target_cols, drop_first, min_freq, other_label)

        elif method == "label":
            result_df, mappings = _label_encode(df, target_cols, min_freq, other_label)

        elif method == "ordinal":
            result_df, mappings = _ordinal_encode(df, target_cols, order)

        elif method == "frequency":
            result_df, mappings = _frequency_encode(df, target_cols)

        elif method == "target":
            if not target_col:
                raise ValueError("method='target'일 때 target 컬럼을 지정해주세요.")
            result_df, mappings = _target_encode(df, target_cols, target_col)

        else:
            raise ValueError(f"지원하지 않는 method입니다: {method}. "
                           "onehot|label|ordinal|frequency|target 중 선택하세요.")

        n_cols_after = len(result_df.columns)

        meta = {
            "method": method,
            "encoded_columns": target_cols,
            "unique_counts": unique_counts,
            "drop_first": drop_first if method == "onehot" else None,
            "min_frequency": min_freq,
            "cols_before": n_cols_before,
            "cols_after": n_cols_after,
            "cols_added": n_cols_after - n_cols_before,
            "rows": int(len(result_df)),
            "mappings_summary": {k: len(v) for k, v in mappings.items()} if mappings else None,
        }

        return result_df, meta

    def description_builder(_df: pd.DataFrame, _result_obj: Any, meta: Dict[str, Any]) -> str:
        parts = []

        method_names = {
            "onehot": "원-핫 인코딩",
            "label": "레이블 인코딩",
            "ordinal": "순서형 인코딩",
            "frequency": "빈도 인코딩",
            "target": "타겟 인코딩",
        }
        method = meta.get("method", "")
        method_desc = method_names.get(method, method)

        parts.append(f"{method_desc}을 수행했습니다.")
        parts.append(f"인코딩된 컬럼: {len(meta['encoded_columns'])}개")

        if method == "onehot":
            parts.append(f"컬럼 수: {meta['cols_before']} → {meta['cols_after']} (+{meta['cols_added']})")
            if meta.get("drop_first"):
                parts.append("(다중공선성 방지를 위해 첫 범주 제외)")

        unique = meta.get("unique_counts", {})
        if unique:
            unique_str = ", ".join([f"{k}({v}개)" for k, v in list(unique.items())[:3]])
            parts.append(f"범주 수: {unique_str}")

        parts.append(f"결과: {meta['rows']}행 × {meta['cols_after']}열")

        return " ".join(parts)

    return safe_run_tool(
        raw_args=args,
        core_fn=core_fn,
        title="encode_categorical",
        ext="csv",
        description_builder=description_builder,
    )
