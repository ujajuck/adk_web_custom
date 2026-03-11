from __future__ import annotations

from typing import Any, Dict, List, Optional, Sequence, Union

import numpy as np
import pandas as pd
import plotly.graph_objects as go

from ..utils.plot_io import save_outputs_and_build_response, make_job_id
from ..schema.line_chart_request import LineChartRequest, LinePlotSegment


def line_plot(
    source: Optional[Dict[str, Any]] = None,
    title: str = "Line Plot",
    x_mode: str = "concat",
    markers: bool = False,
    fill: Optional[str] = None,
    add_boundaries: bool = True,
    hovermode: str = "x unified",
) -> Dict[str, Any]:
    """선 그래프(Line Plot)를 생성하여 JSON으로 저장하고 resource_link를 반환합니다.

    데이터 소스 지정 방식:
      1. direct (Segment 형식):
         source={
           "source_type": "direct",
           "segments": [{"name": "data", "x": [1,2,3], "y_series": {"sales": [10,20,30]}}]
         }

      2. artifact (ADK 아티팩트에서 로드):
         source={
           "source_type": "artifact",
           "artifact_name": "timeseries.csv",
           "x_col": "date",
           "y_cols": ["sales", "revenue"]
         }

      3. file (로컬 파일에서 로드):
         source={
           "source_type": "file",
           "path": "/data/timeseries.csv",
           "x_col": "date",
           "y_cols": ["sales"]
         }

    Args:
        source: 데이터 소스 객체 (위 형식 중 하나)
        title: 그래프 제목
        x_mode: 여러 세그먼트 병합 방식 (concat, align, keep)
        markers: 마커 표시 여부
        fill: 채우기 옵션 (none, tozeroy, tonexty)
        add_boundaries: 경계선 추가 여부
        hovermode: 호버 모드

    Returns:
        {"status": "success", "outputs": [...], "description": "..."}

    Example:
        # Segment 형식 직접 전달
        line_plot(source={
            "source_type": "direct",
            "segments": [{"name": "data", "x": ["Jan", "Feb"], "y_series": {"sales": [100, 150]}}]
        })

        # 아티팩트 사용 (ADK callback이 user_id, session_id 자동 주입)
        line_plot(source={
            "source_type": "artifact",
            "artifact_name": "timeseries.csv",
            "x_col": "date",
            "y_cols": ["sales", "revenue"]
        })
    """
    if source is None:
        raise ValueError("source가 필요합니다.")

    request = LineChartRequest(
        source=source,
        title=title,
        x_mode=x_mode,
        markers=markers,
        fill=fill,
        add_boundaries=add_boundaries,
        hovermode=hovermode,
    )

    segments = request.resolve_segments()
    if not segments:
        raise ValueError("데이터 세그먼트가 비어있습니다.")

    fig = go.Figure()
    mode = "lines+markers" if request.markers else "lines"
    all_trends = []

    for seg in segments:
        for y_name, y_values in seg.y_series.items():
            trace_name = f"{seg.name} - {y_name}" if len(seg.y_series) > 1 else y_name

            # x, y 값 준비
            x_vals = [str(v) for v in seg.x]
            y_vals = [float(v) if v is not None and not np.isnan(v) else None for v in y_values]

            trace_kwargs = dict(
                x=x_vals,
                y=y_vals,
                mode=mode,
                name=trace_name,
            )

            if request.fill:
                trace_kwargs["fill"] = request.fill

            fig.add_trace(go.Scatter(**trace_kwargs))

            # 트렌드 분석
            y_array = np.array([v for v in y_vals if v is not None])
            if len(y_array) > 0:
                all_trends.append(_detect_trend(y_array))

    # 레이아웃 설정
    fig.update_layout(
        title=request.title,
        hovermode=request.hovermode,
    )

    # 첫 번째 세그먼트의 x 컬럼명
    x_label = segments[0].name if segments else "x"
    y_columns = []
    for seg in segments:
        y_columns.extend(seg.y_series.keys())
    y_columns = list(set(y_columns))

    fig.update_xaxes(title=x_label)
    fig.update_yaxes(title=y_columns[0] if len(y_columns) == 1 else "값")

    # 트렌드 결정
    trend_counts: Dict[str, int] = {}
    for t in all_trends:
        trend_counts[t] = trend_counts.get(t, 0) + 1
    dominant_trend = max(trend_counts, key=trend_counts.get) if trend_counts else "판단 불가"

    meta = {
        "x": x_label,
        "y_columns": y_columns,
        "n_lines": len(fig.data),
        "n_segments": len(segments),
        "trend": dominant_trend,
    }

    description = f"선 그래프(Line Plot)입니다. {meta['n_lines']}개의 선을 표시했습니다. 전반적인 추세: {dominant_trend}"
    chart_title = request.title or "Line Plot"
    result = {"type": "plotly", "title": chart_title, "fig": fig.to_dict(), "meta": meta}

    job_id = make_job_id()
    return save_outputs_and_build_response(
        job_id=job_id,
        title=chart_title,
        payloads={"json": result},
        description=description,
    )


def _detect_trend(y_vals: np.ndarray) -> str:
    """y값 배열에서 트렌드 감지."""
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
