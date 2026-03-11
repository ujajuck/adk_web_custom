from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import pandas as pd
import plotly.graph_objects as go

from ..utils.plot_io import save_outputs_and_build_response, make_job_id
from ..schema.bar_plot_request import BarPlotRequest


def bar_plot(
    source: Optional[Dict[str, Any]] = None,
    x: Optional[str] = None,
    y: Optional[str] = None,
    columns: Optional[List[str]] = None,
    agg: str = "sum",
    top_k: int = 30,
    sort: str = "desc",
    title: Optional[str] = None,
    null_label: str = "null",
) -> Dict[str, Any]:
    """막대그래프(Plotly)를 생성하여 JSON으로 저장하고 resource_link를 반환합니다.

    데이터 소스 지정 방식:
      1. direct: source={"source_type": "direct", "data": [...]}
      2. artifact: source={"source_type": "artifact", "artifact_name": "..."}
      3. file: source={"source_type": "file", "path": "..."}

    Args:
        source: 데이터 소스 객체
            - direct: {"source_type": "direct", "data": [{"col": val}, ...]}
            - artifact: {"source_type": "artifact", "artifact_name": "sales.csv"}
            - file: {"source_type": "file", "path": "/path/to/file.csv"}
        x: x축(범주) 컬럼명. 없으면 columns[0] 또는 첫 컬럼
        y: y축(수치) 컬럼명. 없으면 빈도(count) 모드
        columns: 사용할 컬럼 목록 (x, y 대신 지정 가능)
        agg: y가 있을 때 집계 방식 (sum, mean, count, median, max, min)
        top_k: 표시할 상위 N개 막대 (기본값 30)
        sort: 정렬 방식 (desc, asc, none)
        title: 그래프 제목
        null_label: 결측값 표시 라벨

    Returns:
        {"status": "success", "outputs": [...], "description": "..."}

    Example:
        # 직접 데이터 전달
        bar_plot(source={"source_type": "direct", "data": [{"cat": "A", "val": 10}]}, x="cat", y="val")
        # 아티팩트 사용 (ADK callback이 user_id, session_id 자동 주입)
        bar_plot(source={"source_type": "artifact", "artifact_name": "sales.csv"}, x="category", y="amount")
    """
    if source is None:
        raise ValueError("source가 필요합니다. (예: source={'source_type': 'direct', 'data': [...]})")

    request = BarPlotRequest(
        source=source,
        x=x,
        y=y,
        columns=columns,
        agg=agg,
        top_k=top_k,
        sort=sort,
        title=title,
        null_label=null_label,
    )

    df = request.resolve_dataframe()
    x_col = request.get_x_column(df)
    y_col = request.get_y_column(df)

    chart_title = request.title or (
        f"Bar Plot: {x_col}" + (f" vs {y_col} ({request.agg})" if y_col else " (count)")
    )

    use_cols = [x_col] + ([y_col] if y_col else [])
    d = df[use_cols].copy()
    d[x_col] = d[x_col].astype("string").fillna(request.null_label)

    s, y_label = _aggregate_series(d, x_col, y_col, request.agg.lower())

    # 정렬
    sort_lower = request.sort.lower()
    if sort_lower == "asc":
        s = s.sort_values(ascending=True)
    elif sort_lower == "desc":
        s = s.sort_values(ascending=False)
    elif sort_lower != "none":
        raise ValueError("sort는 desc|asc|none 중 하나여야 합니다.")

    s = s.head(request.top_k)

    x_labels = [str(i) for i in s.index.tolist()]
    y_vals = np.array([float(v) for v in s.values.tolist()], dtype=float)

    fig = go.Figure(data=[go.Bar(x=x_labels, y=y_vals.tolist(), name=y_label)])
    fig.update_layout(title=chart_title, xaxis_title=x_col, yaxis_title=y_label)

    pattern = _summarize_bar_patterns(y_vals, x_labels, y_label)
    description = _build_description(pattern)

    result = {
        "type": "plotly",
        "title": chart_title,
        "fig": fig.to_dict(),
        "meta": {
            "x": x_col,
            "y": y_col,
            "agg": request.agg if y_col else "count",
            "top_k": request.top_k,
            "sort": request.sort,
            "bars": len(x_labels),
            "pattern": pattern,
        },
    }

    job_id = make_job_id()
    return save_outputs_and_build_response(
        job_id=job_id,
        title=chart_title,
        payloads={"json": result},
        description=description,
    )


def _aggregate_series(d: pd.DataFrame, x_col: str, y_col: Optional[str], agg: str) -> Tuple[pd.Series, str]:
    if y_col:
        d[y_col] = pd.to_numeric(d[y_col], errors="coerce")
        grp = d.groupby(x_col, dropna=False)[y_col]
        agg_funcs = {
            "sum": grp.sum,
            "mean": grp.mean,
            "count": grp.count,
            "median": grp.median,
            "max": grp.max,
            "min": grp.min,
        }
        if agg not in agg_funcs:
            raise ValueError("agg는 sum|mean|count|median|max|min 중 하나여야 합니다.")
        s = agg_funcs[agg]().dropna()
        return s, f"{y_col} ({agg})"

    s = d.groupby(x_col, dropna=False).size()
    return s, "count"


def _summarize_bar_patterns(values: np.ndarray, labels: list, y_label: str) -> Dict[str, Any]:
    if values.size == 0:
        return {"bars": 0, "sum": 0.0, "top1": None}

    v = values.astype(float)
    v_nonneg = np.clip(v, 0, None)
    total = float(np.sum(v_nonneg))
    bars = int(len(v))

    top1 = (labels[0], float(v[0]))
    top2 = (labels[1], float(v[1])) if bars >= 2 else None

    def share(k: int) -> Optional[float]:
        if total <= 0:
            return None
        return float(np.sum(v_nonneg[: min(k, bars)]) / total)

    top1_share = share(1)
    top3_share = share(3)

    ratio = None
    if top2 and abs(top2[1]) > 1e-12:
        ratio = float(top1[1] / top2[1])

    is_long_tail = None
    if total > 0 and bars >= 5:
        top20_share = share(max(1, int(np.ceil(bars * 0.2))))
        is_long_tail = bool((top20_share or 0) >= 0.8 or (top3_share or 0) >= 0.6)

    return {
        "bars": bars,
        "sum": total,
        "y_label": y_label,
        "top1": {"label": top1[0], "value": top1[1]},
        "top2": {"label": top2[0], "value": top2[1]} if top2 else None,
        "top1_share": top1_share,
        "top3_share": top3_share,
        "ratio_top1_top2": ratio,
        "is_long_tail": is_long_tail,
    }


def _build_description(p: Dict[str, Any]) -> str:
    bars = p.get("bars", 0)
    if bars == 0:
        return "막대그래프(Plotly)입니다. 표시할 막대가 없습니다."

    top1 = p.get("top1") or {}
    parts = [f"막대그래프(Plotly)입니다. 막대 {bars}개를 표시했습니다."]
    parts.append(f"가장 큰 막대는 '{top1.get('label')}' 입니다.")

    if p.get("top1_share"):
        parts.append(f"1위 항목이 전체의 약 {p['top1_share'] * 100:.1f}%를 차지합니다.")
    if p.get("top3_share"):
        parts.append(f"상위 3개가 전체의 약 {p['top3_share'] * 100:.1f}%를 차지합니다.")

    if p.get("is_long_tail") is True:
        parts.append("상위 일부 막대에 값이 집중되는 롱테일(쏠림) 패턴이 보입니다.")
    elif p.get("is_long_tail") is False:
        parts.append("값이 비교적 분산된 편입니다.")

    return " ".join(parts)
