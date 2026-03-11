from __future__ import annotations

from typing import Any, Dict, List, Optional

import numpy as np
import pandas as pd
import plotly.graph_objects as go

from ..utils.plot_io import save_outputs_and_build_response, make_job_id
from ..schema.base_source import resolve_dataframe


def box_plot(
    source: Optional[Dict[str, Any]] = None,
    columns: Optional[List[str]] = None,
    group_by: Optional[str] = None,
    title: Optional[str] = None,
    orientation: str = "v",
    show_points: str = "outliers",
) -> Dict[str, Any]:
    """박스플롯(Box Plot)을 생성하여 데이터 분포와 이상치를 시각화합니다.

    데이터 소스 지정 방식:
      1. direct: source={"source_type": "direct", "data": [...]}
      2. artifact: source={"source_type": "artifact", "artifact_name": "..."}
      3. file: source={"source_type": "file", "path": "..."}

    Args:
        source: 데이터 소스 객체
        columns: 박스플롯을 그릴 수치형 컬럼 목록 (없으면 모든 수치형 컬럼)
        group_by: 그룹별로 나눌 범주형 컬럼명
        title: 그래프 제목
        orientation: 박스 방향 ("v": 수직, "h": 수평)
        show_points: 포인트 표시 옵션 ("outliers", "all", "suspectedoutliers", False)

    Returns:
        {"status": "success", "outputs": [...], "description": "..."}

    Example:
        box_plot(
            source={"source_type": "artifact", "artifact_name": "sales.csv"},
            columns=["price", "quantity"],
            group_by="category"
        )
    """
    if source is None:
        raise ValueError("source가 필요합니다.")

    df = resolve_dataframe(source)
    if df is None or df.empty:
        raise ValueError("데이터가 비어있습니다.")

    # 수치형 컬럼 선택
    numeric_cols = df.select_dtypes(include=[np.number]).columns.tolist()

    if columns:
        # 지정된 컬럼 중 수치형만
        target_cols = [c for c in columns if c in numeric_cols]
    else:
        target_cols = numeric_cols

    if not target_cols:
        raise ValueError("박스플롯을 그릴 수치형 컬럼이 없습니다.")

    chart_title = title or f"Box Plot: {', '.join(target_cols[:3])}" + (f" (외 {len(target_cols)-3}개)" if len(target_cols) > 3 else "")

    fig = go.Figure()
    stats_list = []

    if group_by and group_by in df.columns:
        # 그룹별 박스플롯
        groups = df[group_by].dropna().unique()
        for col in target_cols:
            for grp in groups:
                grp_data = df[df[group_by] == grp][col].dropna()
                if len(grp_data) > 0:
                    if orientation == "h":
                        fig.add_trace(go.Box(
                            x=grp_data.tolist(),
                            name=f"{col} ({grp})",
                            boxpoints=show_points,
                        ))
                    else:
                        fig.add_trace(go.Box(
                            y=grp_data.tolist(),
                            name=f"{col} ({grp})",
                            boxpoints=show_points,
                        ))
                    stats_list.append(_calc_box_stats(grp_data, f"{col} ({grp})"))
    else:
        # 컬럼별 박스플롯
        for col in target_cols:
            col_data = df[col].dropna()
            if len(col_data) > 0:
                if orientation == "h":
                    fig.add_trace(go.Box(
                        x=col_data.tolist(),
                        name=col,
                        boxpoints=show_points,
                    ))
                else:
                    fig.add_trace(go.Box(
                        y=col_data.tolist(),
                        name=col,
                        boxpoints=show_points,
                    ))
                stats_list.append(_calc_box_stats(col_data, col))

    fig.update_layout(
        title=chart_title,
        showlegend=True,
    )

    # 이상치 탐지 요약
    total_outliers = sum(s.get("n_outliers", 0) for s in stats_list)
    skewed_cols = [s["name"] for s in stats_list if abs(s.get("skewness", 0)) > 1]

    meta = {
        "columns": target_cols,
        "group_by": group_by,
        "n_boxes": len(fig.data),
        "stats": stats_list,
        "total_outliers": total_outliers,
        "skewed_columns": skewed_cols,
    }

    description = _build_box_description(meta)
    result = {"type": "plotly", "title": chart_title, "fig": fig.to_dict(), "meta": meta}

    job_id = make_job_id()
    return save_outputs_and_build_response(
        job_id=job_id,
        title=chart_title,
        payloads={"json": result},
        description=description,
    )


def _calc_box_stats(data: pd.Series, name: str) -> Dict[str, Any]:
    """박스플롯 통계 계산."""
    arr = data.to_numpy()
    q1 = float(np.percentile(arr, 25))
    q2 = float(np.percentile(arr, 50))
    q3 = float(np.percentile(arr, 75))
    iqr = q3 - q1

    lower_fence = q1 - 1.5 * iqr
    upper_fence = q3 + 1.5 * iqr

    outliers = arr[(arr < lower_fence) | (arr > upper_fence)]

    # 왜도 계산
    mean = float(np.mean(arr))
    std = float(np.std(arr))
    skewness = float(np.mean(((arr - mean) / (std + 1e-10)) ** 3)) if std > 0 else 0.0

    return {
        "name": name,
        "min": float(np.min(arr)),
        "q1": q1,
        "median": q2,
        "q3": q3,
        "max": float(np.max(arr)),
        "iqr": iqr,
        "lower_fence": lower_fence,
        "upper_fence": upper_fence,
        "n_outliers": int(len(outliers)),
        "outliers_pct": float(len(outliers) / len(arr) * 100),
        "skewness": skewness,
        "mean": mean,
        "std": std,
    }


def _build_box_description(meta: Dict[str, Any]) -> str:
    """박스플롯 설명 생성."""
    parts = [f"박스플롯(Box Plot)입니다. {meta['n_boxes']}개의 박스를 표시했습니다."]

    if meta["total_outliers"] > 0:
        parts.append(f"총 {meta['total_outliers']}개의 이상치가 감지되었습니다.")

    if meta["skewed_columns"]:
        parts.append(f"비대칭 분포: {', '.join(meta['skewed_columns'][:3])}")

    # 가장 변동성 큰 컬럼
    stats = meta.get("stats", [])
    if stats:
        max_std = max(stats, key=lambda x: x.get("std", 0))
        parts.append(f"가장 변동성이 큰 항목: '{max_std['name']}' (표준편차: {max_std['std']:.2f})")

    return " ".join(parts)
