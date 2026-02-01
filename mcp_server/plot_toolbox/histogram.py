from __future__ import annotations

from typing import Any, Dict, Optional, Tuple

import numpy as np
import pandas as pd
import plotly.graph_objects as go

from ..utils.plot_io import safe_run_tool


def histogram(args: Dict[str, Any]) -> Dict[str, Any]:
    """히스토그램(Plotly)을 생성해 JSON으로 저장하고 resource_link로 반환한다.

    description은 '그래프에서 보이는 패턴'만 담는다(왜도/첨도/꼬리/다봉성/집중도 등).
    원인 분석/검정/모델링은 ml_toolbox로 분리한다.

    입력 예시:
      - direct:
        {"kind":"direct","data":[{"x":1},{"x":2},{"x":3}],"columns":["x"],"bins":30}
      - locator(LLM이 채우는 필드: artifact_name/file_name):
        {"kind":"locator","artifact_locator":{"artifact_name":"pokemon_data","file_name":"pokemon.csv"},"columns":["HP"],"bins":40}

    파라미터(수치형):
      - bins (int, default=30)
      - range_min/range_max (float, optional): 둘 다 지정 시 범위 고정
      - density (bool, default=False)
      - log_y (bool, default=False)

    파라미터(범주형):
      - top_k (int, default=30): 상위 N개 카테고리만 표시
      - other_label (str, default="(others)"): top_k 밖을 묶을 라벨

    공통:
      - title (str, optional)
      - null_label (str, default="null")
      - numeric_ratio_threshold (float, default=0.6): 수치형 판정 기준

    출력(JSON 파일 내용):
      {
        "type":"plotly",
        "title":"...",
        "fig": <plotly figure dict>,
        "meta": {
          "mode": "numeric"|"categorical",
          "column": "...",
          ...
        }
      }
    """

    def _pick_column(df: pd.DataFrame, columns: Optional[list], raw_args: Dict[str, Any]) -> str:
        # 우선순위: raw_args["column"] -> columns[0] -> "x" -> 첫 컬럼
        c = raw_args.get("column")
        if isinstance(c, str) and c in df.columns:
            return c
        if columns and len(columns) > 0 and isinstance(columns[0], str) and columns[0] in df.columns:
            return columns[0]
        if "x" in df.columns:
            return "x"
        return df.columns[0]

    def _skewness(x: np.ndarray) -> Optional[float]:
        if x.size < 3:
            return None
        m = float(np.mean(x))
        s = float(np.std(x, ddof=0))
        if s < 1e-12:
            return 0.0
        return float(np.mean(((x - m) / s) ** 3))

    def _kurtosis_excess(x: np.ndarray) -> Optional[float]:
        # Fisher excess kurtosis (normal=0)
        if x.size < 4:
            return None
        m = float(np.mean(x))
        s = float(np.std(x, ddof=0))
        if s < 1e-12:
            return 0.0
        return float(np.mean(((x - m) / s) ** 4) - 3.0)

    def _peak_count(counts: np.ndarray) -> int:
        # 매우 단순한 다봉성(피크 개수) 휴리스틱
        if counts.size < 3:
            return int(np.count_nonzero(counts))
        peaks = 0
        for i in range(1, len(counts) - 1):
            if counts[i] > counts[i - 1] and counts[i] > counts[i + 1] and counts[i] > 0:
                peaks += 1
        return peaks

    def _numeric_description(meta: Dict[str, Any]) -> str:
        col = meta["column"]
        n = meta["n"]
        n_missing = meta["n_missing"]
        skew = meta.get("skewness")
        kurt = meta.get("kurtosis_excess")
        peaks = meta.get("peak_count")
        tail = meta.get("tail_shape")

        parts = []
        parts.append(f"히스토그램(Plotly)입니다. 컬럼='{col}', 유효값={n}개, 결측={n_missing}개.")
        if skew is not None:
            if skew >= 0.5:
                parts.append("오른쪽 꼬리가 긴(양의 왜도) 분포 경향이 보입니다.")
            elif skew <= -0.5:
                parts.append("왼쪽 꼬리가 긴(음의 왜도) 분포 경향이 보입니다.")
            else:
                parts.append("왜도는 크지 않아 비교적 대칭에 가깝습니다.")
        if kurt is not None:
            if kurt >= 1.0:
                parts.append("첨도가 높아 중심이 뾰족하거나 꼬리가 두꺼운 경향이 있습니다.")
            elif kurt <= -1.0:
                parts.append("첨도가 낮아 비교적 평평한(완만한) 분포 경향이 있습니다.")
        if isinstance(peaks, int):
            if peaks >= 2:
                parts.append(f"피크가 {peaks}개로 다봉성(여러 군집) 가능성이 보입니다.")
            elif peaks == 1:
                parts.append("단일 피크 중심의 분포로 보입니다.")
        if tail:
            parts.append(tail)
        return " ".join(parts)

    def _categorical_description(meta: Dict[str, Any]) -> str:
        col = meta["column"]
        bars = meta["bars"]
        n_total = meta["n_total"]
        n_missing = meta["n_missing"]
        top1 = meta.get("top1")
        top1_share = meta.get("top1_share")
        top3_share = meta.get("top3_share")
        is_long_tail = meta.get("is_long_tail")

        parts = []
        parts.append(f"범주형 히스토그램(빈도 막대)입니다. 컬럼='{col}', 표시 막대={bars}개.")
        parts.append(f"전체={n_total}개 중 결측={n_missing}개입니다.")
        if top1:
            parts.append(f"가장 빈도가 높은 항목은 '{top1['label']}' 입니다.")
        if top1_share is not None:
            parts.append(f"1위 항목이 전체의 약 {top1_share*100:.1f}%를 차지합니다.")
        if top3_share is not None:
            parts.append(f"상위 3개가 전체의 약 {top3_share*100:.1f}%를 차지합니다.")
        if is_long_tail is True:
            parts.append("상위 일부 항목에 빈도가 집중되는 롱테일(쏠림) 패턴이 보입니다.")
        elif is_long_tail is False:
            parts.append("빈도가 특정 소수에 과도하게 쏠리기보다는 비교적 분산된 편입니다.")
        return " ".join(parts)

    def core_fn(df: pd.DataFrame, columns: Optional[list], raw_args: Dict[str, Any]) -> Tuple[Dict[str, Any], Dict[str, Any]]:
        if df is None or df.empty:
            raise ValueError("입력 데이터가 비어있습니다.")

        col = _pick_column(df, columns, raw_args)
        title = raw_args.get("title") or f"Histogram: {col}"
        null_label = str(raw_args.get("null_label", "null"))

        s = df[col]
        n_total = int(len(s))
        n_missing = int(s.isna().sum())

        # 수치형 판정
        s_num = pd.to_numeric(s, errors="coerce")
        n_num = int(s_num.notna().sum())
        denom = max(1, (n_total - n_missing))
        numeric_ratio = n_num / denom
        thr = float(raw_args.get("numeric_ratio_threshold", 0.6))
        is_numeric = numeric_ratio >= thr

        if is_numeric:
            vals = s_num.dropna().astype(float).to_numpy()

            bins = int(raw_args.get("bins", 30))
            if bins <= 0:
                raise ValueError("bins는 1 이상의 정수여야 합니다.")

            density = bool(raw_args.get("density", False))
            log_y = bool(raw_args.get("log_y", False))

            rmin = raw_args.get("range_min", None)
            rmax = raw_args.get("range_max", None)
            hist_range = None
            if rmin is not None or rmax is not None:
                if rmin is None or rmax is None:
                    raise ValueError("range_min/range_max는 둘 다 지정하거나 둘 다 생략해야 합니다.")
                hist_range = (float(rmin), float(rmax))

            counts, edges = np.histogram(vals, bins=bins, range=hist_range, density=density)

            # Plotly histogram은 raw를 넣어도 되지만, bins/범위 통제를 위해 bar로 구성
            centers = (edges[:-1] + edges[1:]) / 2.0
            fig = go.Figure(data=[go.Bar(x=centers.tolist(), y=counts.tolist(), name="hist")])
            fig.update_layout(title=title, xaxis_title=col, yaxis_title=("density" if density else "count"))
            if log_y:
                fig.update_yaxes(type="log")

            skew = _skewness(vals)
            kurt = _kurtosis_excess(vals)
            peaks = _peak_count(np.array(counts))

            # tail shape 힌트(꼬리)
            tail_hint = None
            if skew is not None:
                if skew >= 1.0:
                    tail_hint = "큰 값 쪽(오른쪽)에 드문 값이 길게 이어지는 꼬리가 관찰될 수 있습니다."
                elif skew <= -1.0:
                    tail_hint = "작은 값 쪽(왼쪽)에 드문 값이 길게 이어지는 꼬리가 관찰될 수 있습니다."

            meta = {
                "mode": "numeric",
                "column": col,
                "n_total": n_total,
                "n_missing": n_missing,
                "n": int(vals.size),
                "bins": bins,
                "density": density,
                "log_y": log_y,
                "range": [hist_range[0], hist_range[1]] if hist_range else None,
                "skewness": skew,
                "kurtosis_excess": kurt,
                "peak_count": int(peaks),
                "tail_shape": tail_hint,
            }

            result = {"type": "plotly", "title": title, "fig": fig.to_dict(), "meta": meta}
            return result, meta

        # 범주형
        top_k = int(raw_args.get("top_k", 30))
        if top_k <= 0:
            raise ValueError("top_k는 1 이상의 정수여야 합니다.")
        other_label = str(raw_args.get("other_label", "(others)"))

        cat = s.astype("string").fillna(null_label)
        vc = cat.value_counts(dropna=False)

        top = vc.head(top_k)
        rest = vc.iloc[top_k:]
        if len(rest) > 0:
            top.loc[other_label] = int(rest.sum())

        labels = [str(i) for i in top.index.tolist()]
        values = np.array([int(v) for v in top.values.tolist()], dtype=float)

        fig = go.Figure(data=[go.Bar(x=labels, y=values.tolist(), name="count")])
        fig.update_layout(title=title, xaxis_title=col, yaxis_title="count")

        total = float(np.sum(values))
        top1_share = float(values[0] / total) if total > 0 else None
        top3_share = float(np.sum(values[: min(3, len(values))]) / total) if total > 0 else None

        is_long_tail = None
        if total > 0 and len(values) >= 5:
            top20 = max(1, int(np.ceil(len(values) * 0.2)))
            top20_share = float(np.sum(values[:top20]) / total)
            is_long_tail = bool(top20_share >= 0.8 or (top3_share is not None and top3_share >= 0.6))

        meta = {
            "mode": "categorical",
            "column": col,
            "n_total": n_total,
            "n_missing": n_missing,
            "bars": int(len(labels)),
            "top_k": top_k,
            "top1": {"label": labels[0], "value": float(values[0])} if len(labels) > 0 else None,
            "top1_share": top1_share,
            "top3_share": top3_share,
            "is_long_tail": is_long_tail,
        }

        result = {"type": "plotly", "title": title, "fig": fig.to_dict(), "meta": meta}
        return result, meta

    def description_builder(_df: pd.DataFrame, _result_obj: Dict[str, Any], meta: Dict[str, Any]) -> str:
        if meta.get("mode") == "numeric":
            return _numeric_description(meta)
        return _categorical_description(meta)

    return safe_run_tool(
        raw_args=args,
        core_fn=core_fn,
        title="histogram",
        ext="json",
        description_builder=description_builder,
    )
