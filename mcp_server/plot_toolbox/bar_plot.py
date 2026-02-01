from __future__ import annotations

from typing import Any, Dict, Optional, Tuple

import numpy as np
import pandas as pd
import plotly.graph_objects as go

from ..utils.plot_io import safe_run_tool


def bar_plot(args: Dict[str, Any]) -> Dict[str, Any]:
    """막대그래프(Plotly)를 생성해 JSON으로 저장하고 resource_link로 반환한다.

    입력(공통):
      - direct:
        {"kind":"direct","data":[{"a":"A","v":3},{"a":"B","v":7}],"x":"a","y":"v","agg":"sum"}
      - locator(LLM이 채우는 필드: artifact_name/file_name):
        {"kind":"locator","artifact_locator":{"artifact_name":"xxx","file_name":"yyy.csv"},"x":"colA","y":"colB"}

    파라미터:
      - x (str, optional): x축(범주) 컬럼명. 없으면 columns[0] 또는 첫 컬럼
      - y (str, optional): y축(수치) 컬럼명. 없으면 count 모드(빈도)
      - agg (str, default="sum"): y가 있을 때 집계: sum|mean|count|median|max|min
      - top_k (int, default=30): 표시할 상위 N개
      - sort (str, default="desc"): desc|asc|none
      - title (str, optional): 그래프 제목
      - null_label (str, default="null"): 결측 범주 라벨

    출력(JSON 파일 내용):
      {
        "type":"plotly",
        "title":"...",
        "fig": <plotly figure dict>,
        "meta": {...}  
      }
    """

    def _pick_x(df: pd.DataFrame, raw_args: Dict[str, Any], columns: Optional[list]) -> str:
        x = raw_args.get("x")
        if isinstance(x, str) and x in df.columns:
            return x
        if columns and isinstance(columns[0], str) and columns[0] in df.columns:
            return columns[0]
        return df.columns[0]

    def _pick_y(df: pd.DataFrame, raw_args: Dict[str, Any]) -> Optional[str]:
        y = raw_args.get("y")
        if isinstance(y, str) and y in df.columns:
            return y
        return None

    def _aggregate_series(d: pd.DataFrame, x_col: str, y_col: Optional[str], agg: str) -> Tuple[pd.Series, str]:
        """표현을 위한 최소 집계."""
        if y_col:
            d[y_col] = pd.to_numeric(d[y_col], errors="coerce")
            grp = d.groupby(x_col, dropna=False)[y_col]
            agg = agg.lower()
            if agg == "sum":
                s = grp.sum()
            elif agg == "mean":
                s = grp.mean()
            elif agg == "count":
                s = grp.count()
            elif agg == "median":
                s = grp.median()
            elif agg == "max":
                s = grp.max()
            elif agg == "min":
                s = grp.min()
            else:
                raise ValueError("agg는 sum|mean|count|median|max|min 중 하나여야 합니다.")
            s = s.dropna()
            y_label = f"{y_col} ({agg})"
            return s, y_label

        # y가 없으면 빈도(count)
        s = d.groupby(x_col, dropna=False).size()
        return s, "count"

    def _summarize_bar_patterns(values: np.ndarray, labels: list, y_label: str) -> Dict[str, Any]:
        """막대 분포의 '시각적 패턴' 요약용 지표."""
        if values.size == 0:
            return {
                "bars": 0,
                "sum": 0.0,
                "top1": None,
                "top2": None,
                "top1_share": None,
                "top3_share": None,
                "top10_share": None,
                "ratio_top1_top2": None,
                "gini_like": None,
                "is_long_tail": None,
            }

        v = values.astype(float)
        v_nonneg = np.clip(v, 0, None)  # "집중도"는 표현을 위해 비음수만 보는데 수정이 필요할까
        total = float(np.sum(v_nonneg))
        bars = int(len(v))

        # top 정보
        top1_idx = 0
        top2_idx = 1 if bars >= 2 else None
        top1 = (labels[top1_idx], float(v[top1_idx]))
        top2 = (labels[top2_idx], float(v[top2_idx])) if top2_idx is not None else None

        def share(k: int) -> Optional[float]:
            if total <= 0:
                return None
            kk = min(k, bars)
            return float(np.sum(v_nonneg[:kk]) / total)

        top1_share = share(1)
        top3_share = share(3)
        top10_share = share(10)

        ratio_top1_top2 = None
        if top2 is not None and abs(top2[1]) > 1e-12:
            ratio_top1_top2 = float(top1[1] / top2[1])

        is_long_tail = None
        if total > 0 and bars >= 5:
            top20_share = share(max(1, int(np.ceil(bars * 0.2))))
            is_long_tail = bool((top20_share is not None and top20_share >= 0.8) or (top3_share is not None and top3_share >= 0.6))

        gini_like = None
        if total > 0 and bars >= 2:
            sorted_v = np.sort(v_nonneg)
            cum = np.cumsum(sorted_v)
            A = float(np.sum(cum) / (bars * total) - 0.5 / bars)
            gini_like = float(1.0 - 2.0 * A)

        return {
            "bars": bars,
            "sum": total,
            "y_label": y_label,
            "top1": {"label": top1[0], "value": top1[1]},
            "top2": {"label": top2[0], "value": top2[1]} if top2 else None,
            "top1_share": top1_share,
            "top3_share": top3_share,
            "top10_share": top10_share,
            "ratio_top1_top2": ratio_top1_top2,
            "gini_like": gini_like,
            "is_long_tail": is_long_tail,
        }

    def core_fn(df: pd.DataFrame, columns: Optional[list], raw_args: Dict[str, Any]) -> Tuple[Dict[str, Any], Dict[str, Any]]:
        if df is None or df.empty:
            raise ValueError("입력 데이터가 비어있습니다.")

        x_col = _pick_x(df, raw_args, columns)
        y_col = _pick_y(df, raw_args)

        agg = (raw_args.get("agg") or "sum").strip().lower()
        top_k = int(raw_args.get("top_k", 30))
        sort = (raw_args.get("sort") or "desc").strip().lower()
        null_label = str(raw_args.get("null_label", "null"))
        title = raw_args.get("title") or (
            f"Bar Plot: {x_col}" + (f" vs {y_col} ({agg})" if y_col else " (count)")
        )

        if top_k <= 0:
            raise ValueError("top_k는 1 이상의 정수여야 합니다.")

        use_cols = [x_col] + ([y_col] if y_col else [])
        d = df[use_cols].copy()

        # 범주 처리
        d[x_col] = d[x_col].astype("string").fillna(null_label)

        s, y_label = _aggregate_series(d, x_col=x_col, y_col=y_col, agg=agg)

        # 정렬/슬라이싱
        if sort == "asc":
            s = s.sort_values(ascending=True)
        elif sort == "desc":
            s = s.sort_values(ascending=False)
        elif sort == "none":
            pass
        else:
            raise ValueError("sort는 desc|asc|none 중 하나여야 합니다.")

        s = s.head(top_k)

        x_labels = [str(i) for i in s.index.tolist()]
        y_vals = np.array([float(v) for v in s.values.tolist()], dtype=float)

        fig = go.Figure(
            data=[
                go.Bar(
                    x=x_labels,
                    y=y_vals.tolist(),
                    name=y_label,
                )
            ]
        )
        fig.update_layout(title=title, xaxis_title=x_col, yaxis_title=y_label)

        # 시각적 패턴 요약(설명 생성용)
        pattern = _summarize_bar_patterns(values=y_vals, labels=x_labels, y_label=y_label)

        meta = {
            "x": x_col,
            "y": y_col,
            "agg": agg if y_col else "count",
            "top_k": top_k,
            "sort": sort,
            "rows_in": int(df.shape[0]),
            "cols_in": int(df.shape[1]),
            "bars": int(len(x_labels)),
            "pattern": pattern,
        }

        result = {"type": "plotly", "title": title, "fig": fig.to_dict(), "meta": meta}
        return result, meta

    def description_builder(_df: pd.DataFrame, _result_obj: Dict[str, Any], meta: Dict[str, Any]) -> str:
        p = (meta.get("pattern") or {})
        bars = p.get("bars", 0)
        if bars == 0:
            return "막대그래프(Plotly)입니다. 표시할 막대가 없습니다."

        top1 = p.get("top1") or {}
        top2 = p.get("top2")
        top1_share = p.get("top1_share")
        top3_share = p.get("top3_share")
        gini_like = p.get("gini_like")
        is_long_tail = p.get("is_long_tail")
        ratio = p.get("ratio_top1_top2")

        parts = []
        parts.append(f"막대그래프(Plotly)입니다. 막대 {bars}개를 표시했습니다.")
        parts.append(f"가장 큰 막대는 '{top1.get('label')}' 입니다.")

        if top1_share is not None:
            parts.append(f"1위 항목이 전체의 약 {top1_share * 100:.1f}%를 차지합니다.")
        if top3_share is not None:
            parts.append(f"상위 3개가 전체의 약 {top3_share * 100:.1f}%를 차지합니다.")

        if top2 is not None and ratio is not None:
            # ratio가 음수일 수 있어 절댓값 비교보다 문장만 제공
            parts.append(f"1위/2위 값의 비율은 약 {ratio:.2f}배입니다.")

        if is_long_tail is True:
            parts.append("상위 일부 막대에 값이 집중되는 롱테일(쏠림) 패턴이 보입니다.")
        elif is_long_tail is False:
            parts.append("값이 특정 소수에 과도하게 쏠리기보다는 비교적 분산된 편입니다.")

        if gini_like is not None:
            # 0에 가까울수록 고르게, 1에 가까울수록 쏠림(설명용)
            if gini_like >= 0.6:
                parts.append("막대 높이의 불균등도가 큰 편(강한 쏠림)입니다.")
            elif gini_like <= 0.3:
                parts.append("막대 높이가 비교적 고르게 분포합니다.")
            else:
                parts.append("막대 높이가 중간 정도의 불균등도를 보입니다.")

        return " ".join(parts)

    return safe_run_tool(
        raw_args=args,
        core_fn=core_fn,
        title="bar_plot",
        ext="json",
        description_builder=description_builder,
    )
