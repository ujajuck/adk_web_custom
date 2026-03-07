from __future__ import annotations

from typing import Any, Dict, List, Optional

import plotly.graph_objects as go
from plotly.subplots import make_subplots

from ..utils.plot_io import save_outputs_and_build_response, make_job_id


def combine_plots(
    plots: List[Dict[str, Any]],
    layout: str = "grid",
    rows: Optional[int] = None,
    cols: Optional[int] = None,
    title: str = "Combined Plot",
    shared_xaxes: bool = False,
    shared_yaxes: bool = False,
) -> Dict[str, Any]:
    """여러 Plotly 그래프를 하나로 합칩니다.

    Args:
        plots: 합칠 플롯 목록. 각 항목은 {"fig": <plotly dict>, "title": "..."} 형태
               또는 {"artifact_name": "plot1"} 형태로 아티팩트에서 로드
        layout: 레이아웃 방식 (grid, vertical, horizontal)
        rows: 그리드 레이아웃일 때 행 수 (없으면 자동 계산)
        cols: 그리드 레이아웃일 때 열 수 (없으면 자동 계산)
        title: 합친 그래프 제목
        shared_xaxes: x축 공유 여부
        shared_yaxes: y축 공유 여부

    Returns:
        {"status": "success", "outputs": [...], "description": "..."}

    Example:
        combine_plots(
            plots=[
                {"fig": fig1_dict, "title": "Sales"},
                {"fig": fig2_dict, "title": "Revenue"}
            ],
            layout="grid",
            cols=2,
            title="Sales & Revenue Dashboard"
        )
    """
    if not plots:
        raise ValueError("합칠 플롯이 없습니다.")

    n_plots = len(plots)

    # 레이아웃 계산
    if layout == "vertical":
        n_rows, n_cols = n_plots, 1
    elif layout == "horizontal":
        n_rows, n_cols = 1, n_plots
    else:  # grid
        if rows and cols:
            n_rows, n_cols = rows, cols
        elif rows:
            n_rows = rows
            n_cols = (n_plots + rows - 1) // rows
        elif cols:
            n_cols = cols
            n_rows = (n_plots + cols - 1) // cols
        else:
            # 자동 계산 (정사각형에 가깝게)
            import math
            n_cols = math.ceil(math.sqrt(n_plots))
            n_rows = math.ceil(n_plots / n_cols)

    # 서브플롯 제목 추출
    subplot_titles = []
    for p in plots:
        if isinstance(p, dict):
            subplot_titles.append(p.get("title", ""))
        else:
            subplot_titles.append("")

    # 서브플롯 생성
    fig = make_subplots(
        rows=n_rows,
        cols=n_cols,
        subplot_titles=subplot_titles,
        shared_xaxes=shared_xaxes,
        shared_yaxes=shared_yaxes,
    )

    # 각 플롯의 트레이스 추가
    for idx, p in enumerate(plots):
        row = idx // n_cols + 1
        col = idx % n_cols + 1

        if isinstance(p, dict) and "fig" in p:
            plot_fig = p["fig"]
            if isinstance(plot_fig, dict) and "data" in plot_fig:
                for trace_data in plot_fig["data"]:
                    trace = go.Scatter(**trace_data) if trace_data.get("type", "scatter") == "scatter" else _create_trace(trace_data)
                    fig.add_trace(trace, row=row, col=col)

    fig.update_layout(
        title=title,
        height=300 * n_rows,
        showlegend=True,
    )

    meta = {
        "n_plots": n_plots,
        "layout": layout,
        "rows": n_rows,
        "cols": n_cols,
    }

    description = f"{n_plots}개의 그래프를 {n_rows}x{n_cols} 그리드로 합쳤습니다."
    result = {"type": "plotly", "title": title, "fig": fig.to_dict(), "meta": meta}

    job_id = make_job_id()
    return save_outputs_and_build_response(
        job_id=job_id,
        title=title,
        payloads={"json": result},
        description=description,
    )


def _create_trace(trace_data: Dict[str, Any]) -> Any:
    """트레이스 데이터에서 적절한 Plotly 트레이스 객체 생성."""
    trace_type = trace_data.get("type", "scatter")

    type_map = {
        "scatter": go.Scatter,
        "bar": go.Bar,
        "histogram": go.Histogram,
        "heatmap": go.Heatmap,
        "pie": go.Pie,
        "box": go.Box,
    }

    trace_class = type_map.get(trace_type, go.Scatter)

    # type 키 제거 후 나머지로 트레이스 생성
    trace_kwargs = {k: v for k, v in trace_data.items() if k != "type"}

    try:
        return trace_class(**trace_kwargs)
    except Exception:
        # 실패하면 기본 스캐터로
        return go.Scatter(x=trace_data.get("x", []), y=trace_data.get("y", []))
