from __future__ import annotations

from typing import Any, Dict, List, Optional, Union

import numpy as np
import pandas as pd
import plotly.graph_objects as go

from ..utils.plot_io import save_outputs_and_build_response, make_job_id


def line_plot(
    data: Optional[List[Dict[str, Any]]] = None,
    artifact_name: Optional[str] = None,
    source_type: Optional[str] = None,
    x: Optional[str] = None,
    y: Optional[Union[str, List[str]]] = None,
    columns: Optional[List[str]] = None,
    group_by: Optional[str] = None,
    agg: str = "mean",
    sort_x: bool = True,
    markers: bool = False,
    fill: Optional[str] = None,
    title: Optional[str] = None,
) -> Dict[str, Any]:
    """선 그래프(Line Plot)를 생성하여 JSON으로 저장하고 resource_link를 반환합니다.

    Args:
        data: 데이터 레코드 목록. 예: [{"date": "2024-01", "sales": 100}, ...]
        artifact_name: ADK 아티팩트 이름 (예: "timeseries.csv"). data 대신 사용 가능
        source_type: 데이터 소스 타입. "artifact"면 artifact_name 사용
        x: x축 컬럼명 (날짜/시간 또는 순서형)
        y: y축 컬럼명 (단일 문자열 또는 여러 컬럼의 리스트)
        columns: 사용할 컬럼 목록 (x, y 대신 지정 가능)
        group_by: 그룹별로 선을 분리할 범주형 컬럼
        agg: x축 값 중복 시 집계 방법 (sum, mean, median, max, min, count)
        sort_x: x축 기준 정렬 여부
        markers: 마커 표시 여부
        fill: 채우기 옵션 (none, tozeroy, tonexty)
        title: 그래프 제목

    Returns:
        {"status": "success", "outputs": [...], "description": "..."}

    Example:
        # 직접 데이터 전달
        line_plot(data=[{"month": "Jan", "sales": 100}], x="month", y="sales")
        # 아티팩트 사용 (ADK callback이 data를 주입)
        line_plot(source_type="artifact", artifact_name="timeseries.csv", x="date", y="value")
    """
    if not data:
        raise ValueError("data가 비어있습니다.")
    df = pd.DataFrame(data)

    # x 컬럼 선택
    x_col = x if x and x in df.columns else (columns[0] if columns and columns[0] in df.columns else df.columns[0])

    # y 컬럼들 파싱
    y_cols = _parse_y_columns(y, df, columns)
    if not y_cols:
        numeric_cols = df.select_dtypes(include=[np.number]).columns.tolist()
        y_cols = [c for c in numeric_cols if c != x_col][:3]

    if not y_cols:
        raise ValueError("y 컬럼을 지정하거나, 수치형 컬럼이 필요합니다.")

    group_col = group_by if group_by and group_by in df.columns else None
    chart_title = title or f"Line Plot: {', '.join(y_cols)} by {x_col}"

    # 데이터 준비
    use_cols = list(set([x_col] + y_cols + ([group_col] if group_col else [])))
    d = df[use_cols].copy()

    for yc in y_cols:
        d[yc] = pd.to_numeric(d[yc], errors="coerce")

    agg_fn = {"sum": "sum", "mean": "mean", "median": "median", "max": "max", "min": "min", "count": "count"}.get(agg.lower(), "mean")

    fig = go.Figure()
    mode = "lines+markers" if markers else "lines"
    all_trends = []

    if group_col:
        for grp in d[group_col].dropna().unique():
            grp_data = d[d[group_col] == grp]
            for yc in y_cols:
                agg_data = grp_data.groupby(x_col, dropna=False)[yc].agg(agg_fn).reset_index()
                if sort_x:
                    agg_data = agg_data.sort_values(x_col)
                x_vals = agg_data[x_col].astype(str).tolist()
                y_vals = agg_data[yc].to_numpy()
                line_name = f"{grp} - {yc}" if len(y_cols) > 1 else str(grp)
                trace_kwargs = dict(x=x_vals, y=y_vals.tolist(), mode=mode, name=line_name)
                if fill:
                    trace_kwargs["fill"] = fill
                fig.add_trace(go.Scatter(**trace_kwargs))
                all_trends.append(_detect_trend(y_vals))
    else:
        for yc in y_cols:
            agg_data = d.groupby(x_col, dropna=False)[yc].agg(agg_fn).reset_index()
            if sort_x:
                agg_data = agg_data.sort_values(x_col)
            x_vals = agg_data[x_col].astype(str).tolist()
            y_vals = agg_data[yc].to_numpy()
            trace_kwargs = dict(x=x_vals, y=y_vals.tolist(), mode=mode, name=yc)
            if fill:
                trace_kwargs["fill"] = fill
            fig.add_trace(go.Scatter(**trace_kwargs))
            all_trends.append(_detect_trend(y_vals))

    fig.update_layout(title=chart_title, xaxis_title=x_col, yaxis_title=y_cols[0] if len(y_cols) == 1 else "값")

    trend_counts = {}
    for t in all_trends:
        trend_counts[t] = trend_counts.get(t, 0) + 1
    dominant_trend = max(trend_counts, key=trend_counts.get) if trend_counts else "판단 불가"

    meta = {
        "x": x_col,
        "y_columns": y_cols,
        "n_lines": len(fig.data),
        "trend": dominant_trend,
    }

    description = f"선 그래프(Line Plot)입니다. {meta['n_lines']}개의 선을 표시했습니다. 전반적인 추세: {dominant_trend}"
    result = {"type": "plotly", "title": chart_title, "fig": fig.to_dict(), "meta": meta}

    job_id = make_job_id()
    return save_outputs_and_build_response(
        job_id=job_id,
        payloads={"json": result},
        description=description,
    )


def _parse_y_columns(y: Union[str, List[str], None], df: pd.DataFrame, columns: Optional[List[str]]) -> List[str]:
    if isinstance(y, str) and y in df.columns:
        return [y]
    if isinstance(y, list):
        return [c for c in y if isinstance(c, str) and c in df.columns]
    if columns and len(columns) >= 2:
        return [c for c in columns[1:] if c in df.columns]
    return []


def _detect_trend(y_vals: np.ndarray) -> str:
    if len(y_vals) < 2:
        return "판단 불가"
    mid = len(y_vals) // 2
    first_half = np.nanmean(y_vals[:mid])
    second_half = np.nanmean(y_vals[mid:])
    if np.isnan(first_half) or np.isnan(second_half):
        return "판단 불가"
    change_pct = (second_half - first_half) / (abs(first_half) + 1e-10) * 100
    if change_pct > 10:
        return "상승 추세"
    elif change_pct < -10:
        return "하락 추세"
    return "횡보/보합"
