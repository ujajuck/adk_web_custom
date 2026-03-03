from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import pandas as pd
import plotly.graph_objects as go

from ..utils.plot_io import save_outputs_and_build_response, make_job_id
from ..schema.scatter_plot_request import ScatterPlotRequest


def scatter_plot(
    source: Optional[Dict[str, Any]] = None,
    x: Optional[str] = None,
    y: Optional[str] = None,
    columns: Optional[List[str]] = None,
    color: Optional[str] = None,
    size: Optional[str] = None,
    trendline: bool = False,
    title: Optional[str] = None,
    opacity: float = 0.7,
    max_points: int = 5000,
) -> Dict[str, Any]:
    """산점도(Scatter Plot)를 생성하여 JSON으로 저장하고 resource_link를 반환합니다.

    데이터 소스 지정 방식:
      1. direct: source={"source_type": "direct", "data": [...]}
      2. artifact: source={"source_type": "artifact", "artifact_name": "..."}
      3. file: source={"source_type": "file", "path": "..."}

    Args:
        source: 데이터 소스 객체
            - direct: {"source_type": "direct", "data": [{"col": val}, ...]}
            - artifact: {"source_type": "artifact", "artifact_name": "data.csv"}
            - file: {"source_type": "file", "path": "/path/to/file.csv"}
        x: x축 컬럼명 (수치형)
        y: y축 컬럼명 (수치형)
        columns: 사용할 컬럼 목록 ([x컬럼, y컬럼] 형태로도 지정 가능)
        color: 점 색상을 구분할 범주형 컬럼
        size: 점 크기를 결정할 수치형 컬럼
        trendline: 회귀 추세선 표시 여부
        title: 그래프 제목
        opacity: 점 투명도 (0~1)
        max_points: 표시할 최대 점 개수 (샘플링)

    Returns:
        {"status": "success", "outputs": [...], "description": "..."}

    Example:
        # 직접 데이터 전달
        scatter_plot(source={"source_type": "direct", "data": [{"age": 25, "income": 50000}]}, x="age", y="income")
        # 아티팩트 사용 (ADK callback이 user_id, session_id 자동 주입)
        scatter_plot(source={"source_type": "artifact", "artifact_name": "data.csv"}, x="age", y="income")
    """
    if source is None:
        raise ValueError("source가 필요합니다. (예: source={'source_type': 'direct', 'data': [...]})")

    request = ScatterPlotRequest(
        source=source,
        x=x,
        y=y,
        columns=columns,
        color=color,
        size=size,
        trendline=trendline,
        title=title,
        opacity=opacity,
        max_points=max_points,
    )

    df = request.resolve_dataframe()
    x_col = request.get_x_column(df)
    y_col = request.get_y_column(df)

    if not x_col or x_col not in df.columns:
        raise ValueError("x 컬럼을 지정해주세요.")
    if not y_col or y_col not in df.columns:
        raise ValueError("y 컬럼을 지정해주세요.")

    chart_title = request.title or f"Scatter Plot: {x_col} vs {y_col}"

    # 데이터 준비
    use_cols = [x_col, y_col]
    if request.color and request.color in df.columns:
        use_cols.append(request.color)
    if request.size and request.size in df.columns:
        use_cols.append(request.size)

    d = df[use_cols].copy()
    d[x_col] = pd.to_numeric(d[x_col], errors="coerce")
    d[y_col] = pd.to_numeric(d[y_col], errors="coerce")
    d = d.dropna(subset=[x_col, y_col])

    n_original = len(d)
    if len(d) > request.max_points:
        d = d.sample(n=request.max_points, random_state=42)
    n_points = len(d)

    if n_points == 0:
        raise ValueError("유효한 데이터 포인트가 없습니다.")

    x_vals = d[x_col].to_numpy()
    y_vals = d[y_col].to_numpy()

    correlation = float(np.corrcoef(x_vals, y_vals)[0, 1]) if n_points >= 2 else None
    correlation_strength = _correlation_strength(correlation) if correlation else None

    fig = go.Figure()

    if request.color and request.color in d.columns:
        for cat in d[request.color].dropna().unique():
            mask = d[request.color] == cat
            scatter_kwargs = dict(
                x=d.loc[mask, x_col].tolist(),
                y=d.loc[mask, y_col].tolist(),
                mode="markers",
                name=str(cat),
                opacity=request.opacity,
            )
            if request.size and request.size in d.columns:
                scatter_kwargs["marker"] = dict(size=_normalize_sizes(d.loc[mask, request.size]))
            fig.add_trace(go.Scatter(**scatter_kwargs))
    else:
        scatter_kwargs = dict(
            x=d[x_col].tolist(),
            y=d[y_col].tolist(),
            mode="markers",
            name="데이터",
            opacity=request.opacity,
        )
        if request.size and request.size in d.columns:
            scatter_kwargs["marker"] = dict(size=_normalize_sizes(d[request.size]))
        fig.add_trace(go.Scatter(**scatter_kwargs))

    slope, intercept = None, None
    if request.trendline:
        slope, intercept = _add_trendline(fig, x_vals, y_vals)

    fig.update_layout(title=chart_title, xaxis_title=x_col, yaxis_title=y_col)

    meta = {
        "x": x_col,
        "y": y_col,
        "n_points": n_points,
        "sampled": n_original > request.max_points,
        "n_original": n_original,
        "correlation": correlation,
        "correlation_strength": correlation_strength,
        "slope": slope,
        "intercept": intercept,
    }

    description = _build_description(meta)
    result = {"type": "plotly", "title": chart_title, "fig": fig.to_dict(), "meta": meta}

    job_id = make_job_id()
    return save_outputs_and_build_response(
        job_id=job_id,
        payloads={"json": result},
        description=description,
    )


def _correlation_strength(r: float) -> str:
    abs_r = abs(r)
    if abs_r >= 0.7:
        strength = "강한"
    elif abs_r >= 0.4:
        strength = "중간 정도의"
    elif abs_r >= 0.2:
        strength = "약한"
    else:
        return "거의 상관 없음"
    direction = "양의" if r > 0 else "음의"
    return f"{strength} {direction} 상관"


def _normalize_sizes(series: pd.Series) -> list:
    sizes = pd.to_numeric(series, errors="coerce").fillna(10)
    size_min, size_max = sizes.min(), sizes.max()
    if size_max > size_min:
        normalized = 5 + 45 * (sizes - size_min) / (size_max - size_min)
    else:
        normalized = pd.Series([15] * len(sizes))
    return normalized.tolist()


def _add_trendline(fig: go.Figure, x: np.ndarray, y: np.ndarray) -> Tuple[float, float]:
    mask = np.isfinite(x) & np.isfinite(y)
    x_clean, y_clean = x[mask], y[mask]
    if len(x_clean) < 2:
        return 0.0, 0.0

    coeffs = np.polyfit(x_clean, y_clean, 1)
    slope, intercept = coeffs[0], coeffs[1]

    x_line = np.array([x_clean.min(), x_clean.max()])
    y_line = slope * x_line + intercept

    fig.add_trace(go.Scatter(
        x=x_line.tolist(),
        y=y_line.tolist(),
        mode="lines",
        name="추세선",
        line=dict(color="red", dash="dash", width=2),
    ))
    return float(slope), float(intercept)


def _build_description(meta: Dict[str, Any]) -> str:
    parts = [f"산점도(Scatter Plot)입니다. {meta['n_points']}개의 점을 표시했습니다."]

    if meta.get("sampled"):
        parts.append(f"(원본 {meta['n_original']}개에서 샘플링)")

    corr = meta.get("correlation")
    strength = meta.get("correlation_strength")
    if corr is not None and strength:
        parts.append(f"상관계수는 {corr:.3f}로, {strength} 관계입니다.")

    if meta.get("slope") is not None and abs(meta["slope"]) > 0.001:
        direction = "증가" if meta["slope"] > 0 else "감소"
        parts.append(f"추세선 기울기: {meta['slope']:.4f} ({direction} 추세)")

    return " ".join(parts)
