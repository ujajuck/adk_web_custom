from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import pandas as pd
import plotly.graph_objects as go

from ..utils.plot_io import save_outputs_and_build_response, make_job_id


def histogram(
    data: List[Dict[str, Any]],
    column: Optional[str] = None,
    columns: Optional[List[str]] = None,
    bins: int = 30,
    title: Optional[str] = None,
    density: bool = False,
    log_y: bool = False,
    range_min: Optional[float] = None,
    range_max: Optional[float] = None,
    top_k: int = 30,
    other_label: str = "(others)",
    null_label: str = "null",
    numeric_ratio_threshold: float = 0.6,
) -> Dict[str, Any]:
    """히스토그램(Plotly)을 생성하여 JSON으로 저장하고 resource_link를 반환합니다.

    Args:
        data: 데이터 레코드 목록. 예: [{"col1": 1, "col2": "a"}, ...]
        column: 히스토그램을 그릴 컬럼명 (단일 컬럼)
        columns: 히스토그램을 그릴 컬럼명 목록 (첫 번째 컬럼 사용)
        bins: 히스토그램 구간 수 (수치형, 기본값 30)
        title: 그래프 제목 (미지정 시 자동 생성)
        density: True면 밀도(비율)로 표시
        log_y: True면 y축 로그 스케일
        range_min: x축 최소값 (range_max와 함께 지정)
        range_max: x축 최대값 (range_min과 함께 지정)
        top_k: 범주형일 때 상위 N개만 표시 (기본값 30)
        other_label: top_k 밖 항목을 묶을 라벨
        null_label: 결측값 표시 라벨
        numeric_ratio_threshold: 수치형 판정 기준 (0~1)

    Returns:
        {"status": "success", "outputs": [...], "description": "..."}

    Example:
        histogram(data=[{"age": 25}, {"age": 30}], column="age", bins=10)
    """
    # DataFrame 생성
    if not data:
        raise ValueError("data가 비어있습니다.")
    df = pd.DataFrame(data)

    # 컬럼 선택
    col = _pick_column(df, column, columns)
    chart_title = title or f"Histogram: {col}"

    s = df[col]
    n_total = int(len(s))
    n_missing = int(s.isna().sum())

    # 수치형 판정
    s_num = pd.to_numeric(s, errors="coerce")
    n_num = int(s_num.notna().sum())
    denom = max(1, (n_total - n_missing))
    numeric_ratio = n_num / denom
    is_numeric = numeric_ratio >= numeric_ratio_threshold

    if is_numeric:
        result, meta = _build_numeric_histogram(
            s_num, col, chart_title, bins, density, log_y, range_min, range_max, n_total, n_missing
        )
        description = _numeric_description(meta)
    else:
        result, meta = _build_categorical_histogram(
            s, col, chart_title, top_k, other_label, null_label, n_total, n_missing
        )
        description = _categorical_description(meta)

    # 저장 및 응답 생성
    job_id = make_job_id()
    return save_outputs_and_build_response(
        job_id=job_id,
        payloads={"json": result},
        description=description,
    )


def _pick_column(df: pd.DataFrame, column: Optional[str], columns: Optional[List[str]]) -> str:
    """컬럼 선택 우선순위: column -> columns[0] -> 'x' -> 첫 컬럼"""
    if column and column in df.columns:
        return column
    if columns and len(columns) > 0 and columns[0] in df.columns:
        return columns[0]
    if "x" in df.columns:
        return "x"
    return df.columns[0]


def _build_numeric_histogram(
    s_num: pd.Series,
    col: str,
    title: str,
    bins: int,
    density: bool,
    log_y: bool,
    range_min: Optional[float],
    range_max: Optional[float],
    n_total: int,
    n_missing: int,
) -> Tuple[Dict[str, Any], Dict[str, Any]]:
    """수치형 히스토그램 생성"""
    vals = s_num.dropna().astype(float).to_numpy()

    if bins <= 0:
        raise ValueError("bins는 1 이상의 정수여야 합니다.")

    hist_range = None
    if range_min is not None or range_max is not None:
        if range_min is None or range_max is None:
            raise ValueError("range_min/range_max는 둘 다 지정하거나 둘 다 생략해야 합니다.")
        hist_range = (float(range_min), float(range_max))

    counts, edges = np.histogram(vals, bins=bins, range=hist_range, density=density)
    centers = (edges[:-1] + edges[1:]) / 2.0

    fig = go.Figure(data=[go.Bar(x=centers.tolist(), y=counts.tolist(), name="hist")])
    fig.update_layout(title=title, xaxis_title=col, yaxis_title=("density" if density else "count"))
    if log_y:
        fig.update_yaxes(type="log")

    skew = _skewness(vals)
    kurt = _kurtosis_excess(vals)
    peaks = _peak_count(np.array(counts))

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


def _build_categorical_histogram(
    s: pd.Series,
    col: str,
    title: str,
    top_k: int,
    other_label: str,
    null_label: str,
    n_total: int,
    n_missing: int,
) -> Tuple[Dict[str, Any], Dict[str, Any]]:
    """범주형 히스토그램 생성"""
    if top_k <= 0:
        raise ValueError("top_k는 1 이상의 정수여야 합니다.")

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


def _skewness(x: np.ndarray) -> Optional[float]:
    if x.size < 3:
        return None
    m = float(np.mean(x))
    s = float(np.std(x, ddof=0))
    if s < 1e-12:
        return 0.0
    return float(np.mean(((x - m) / s) ** 3))


def _kurtosis_excess(x: np.ndarray) -> Optional[float]:
    if x.size < 4:
        return None
    m = float(np.mean(x))
    s = float(np.std(x, ddof=0))
    if s < 1e-12:
        return 0.0
    return float(np.mean(((x - m) / s) ** 4) - 3.0)


def _peak_count(counts: np.ndarray) -> int:
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

    parts = [f"히스토그램(Plotly)입니다. 컬럼='{col}', 유효값={n}개, 결측={n_missing}개."]
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

    parts = [f"범주형 히스토그램(빈도 막대)입니다. 컬럼='{col}', 표시 막대={bars}개."]
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
