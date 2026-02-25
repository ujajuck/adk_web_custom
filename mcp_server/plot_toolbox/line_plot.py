from __future__ import annotations

from typing import Any, Dict, Optional, Tuple, List

import numpy as np
import pandas as pd
import plotly.graph_objects as go

from ..utils.plot_io import safe_run_tool


def line_plot(args: Dict[str, Any]) -> Dict[str, Any]:
    """선 그래프(Line Plot)를 생성해 JSON으로 저장하고 resource_link로 반환한다.

    시계열 데이터나 연속적인 변화를 시각화하는 데 적합하다.
    여러 y 컬럼을 동시에 표시할 수 있다.

    입력 예시:
      - direct:
        {"kind":"direct","data":[{"date":"2024-01","sales":100},{"date":"2024-02","sales":150}],"x":"date","y":"sales"}
      - locator(LLM이 채우는 필드: artifact_name/file_name):
        {"kind":"locator","artifact_locator":{"artifact_name":"monthly_data","file_name":"monthly.csv"},"x":"month","y":["revenue","cost"]}

    파라미터:
      - x (str, required): x축 컬럼명 (날짜/시간 또는 순서형)
      - y (str|list[str], required): y축 컬럼명 (단일 또는 여러 컬럼)
      - group_by (str, optional): 그룹별로 선을 분리할 범주형 컬럼
      - agg (str, default="mean"): x축 값이 중복될 때 집계 방법 (sum|mean|median|max|min|count)
      - sort_x (bool, default=True): x축 기준 정렬 여부
      - markers (bool, default=False): 마커 표시 여부
      - fill (str, optional): 채우기 옵션 (none|tozeroy|tonexty)
      - title (str, optional): 그래프 제목

    출력(JSON 파일 내용):
      {
        "type":"plotly",
        "title":"...",
        "fig": <plotly figure dict>,
        "meta": {
          "x": str,
          "y_columns": list,
          "n_points": int,
          "trend": str,  # "상승"|"하락"|"횡보"
          ...
        }
      }
    """

    def _parse_y_columns(raw_args: Dict[str, Any], df: pd.DataFrame, columns: Optional[list]) -> List[str]:
        """y 컬럼 파싱 (단일 문자열 또는 리스트)."""
        y = raw_args.get("y")

        if isinstance(y, str):
            if y in df.columns:
                return [y]
        elif isinstance(y, list):
            valid = [c for c in y if isinstance(c, str) and c in df.columns]
            if valid:
                return valid

        # columns에서 y 찾기 (x 제외한 나머지)
        if columns and len(columns) >= 2:
            return [c for c in columns[1:] if c in df.columns]

        return []

    def _detect_trend(y_vals: np.ndarray) -> str:
        """단순 추세 감지."""
        if len(y_vals) < 2:
            return "판단 불가"

        # 전반부와 후반부 평균 비교
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
        else:
            return "횡보/보합"

    def _calculate_volatility(y_vals: np.ndarray) -> Optional[float]:
        """변동성(표준편차/평균) 계산."""
        if len(y_vals) < 2:
            return None
        mean = np.nanmean(y_vals)
        std = np.nanstd(y_vals)
        if abs(mean) < 1e-10:
            return None
        return float(std / abs(mean))

    def core_fn(df: pd.DataFrame, columns: Optional[list], raw_args: Dict[str, Any]) -> Tuple[Dict[str, Any], Dict[str, Any]]:
        if df is None or df.empty:
            raise ValueError("입력 데이터가 비어있습니다.")

        # x 컬럼
        x_col = raw_args.get("x")
        if not x_col or x_col not in df.columns:
            if columns and len(columns) >= 1 and columns[0] in df.columns:
                x_col = columns[0]
            else:
                x_col = df.columns[0]

        # y 컬럼들
        y_cols = _parse_y_columns(raw_args, df, columns)
        if not y_cols:
            # x를 제외한 수치형 컬럼 자동 선택
            numeric_cols = df.select_dtypes(include=[np.number]).columns.tolist()
            y_cols = [c for c in numeric_cols if c != x_col][:3]  # 최대 3개

        if not y_cols:
            raise ValueError("y 컬럼을 지정하거나, 수치형 컬럼이 필요합니다.")

        group_col = raw_args.get("group_by")
        if group_col and group_col not in df.columns:
            group_col = None

        agg_method = (raw_args.get("agg") or "mean").strip().lower()
        sort_x = raw_args.get("sort_x", True)
        markers = bool(raw_args.get("markers", False))
        fill = raw_args.get("fill")
        title = raw_args.get("title") or f"Line Plot: {', '.join(y_cols)} by {x_col}"

        # 데이터 준비
        use_cols = [x_col] + y_cols
        if group_col:
            use_cols.append(group_col)

        d = df[list(set(use_cols))].copy()

        # y 컬럼 수치형 변환
        for yc in y_cols:
            d[yc] = pd.to_numeric(d[yc], errors="coerce")

        # 집계 (x축 값이 중복되는 경우)
        agg_funcs = {
            "sum": "sum", "mean": "mean", "median": "median",
            "max": "max", "min": "min", "count": "count"
        }
        agg_fn = agg_funcs.get(agg_method, "mean")

        fig = go.Figure()
        mode = "lines+markers" if markers else "lines"

        all_trends = []
        all_volatilities = []

        if group_col:
            # 그룹별 선 생성
            groups = d[group_col].dropna().unique()
            for grp in groups:
                grp_data = d[d[group_col] == grp]

                for yc in y_cols:
                    agg_data = grp_data.groupby(x_col, dropna=False)[yc].agg(agg_fn).reset_index()
                    if sort_x:
                        agg_data = agg_data.sort_values(x_col)

                    x_vals = agg_data[x_col].astype(str).tolist()
                    y_vals = agg_data[yc].to_numpy()

                    line_name = f"{grp} - {yc}" if len(y_cols) > 1 else str(grp)

                    trace_kwargs = dict(
                        x=x_vals,
                        y=y_vals.tolist(),
                        mode=mode,
                        name=line_name,
                    )
                    if fill:
                        trace_kwargs["fill"] = fill

                    fig.add_trace(go.Scatter(**trace_kwargs))
                    all_trends.append(_detect_trend(y_vals))
                    vol = _calculate_volatility(y_vals)
                    if vol is not None:
                        all_volatilities.append(vol)
        else:
            # 단일 또는 다중 y 컬럼
            for yc in y_cols:
                agg_data = d.groupby(x_col, dropna=False)[yc].agg(agg_fn).reset_index()
                if sort_x:
                    agg_data = agg_data.sort_values(x_col)

                x_vals = agg_data[x_col].astype(str).tolist()
                y_vals = agg_data[yc].to_numpy()

                trace_kwargs = dict(
                    x=x_vals,
                    y=y_vals.tolist(),
                    mode=mode,
                    name=yc,
                )
                if fill:
                    trace_kwargs["fill"] = fill

                fig.add_trace(go.Scatter(**trace_kwargs))
                all_trends.append(_detect_trend(y_vals))
                vol = _calculate_volatility(y_vals)
                if vol is not None:
                    all_volatilities.append(vol)

        fig.update_layout(
            title=title,
            xaxis_title=x_col,
            yaxis_title=y_cols[0] if len(y_cols) == 1 else "값",
        )

        # 전체 추세 판단
        trend_counts = {}
        for t in all_trends:
            trend_counts[t] = trend_counts.get(t, 0) + 1
        dominant_trend = max(trend_counts, key=trend_counts.get) if trend_counts else "판단 불가"

        avg_volatility = float(np.mean(all_volatilities)) if all_volatilities else None

        meta = {
            "x": x_col,
            "y_columns": y_cols,
            "group_by": group_col,
            "agg": agg_method,
            "n_lines": len(fig.data),
            "n_points": int(len(d)),
            "trend": dominant_trend,
            "avg_volatility": avg_volatility,
            "markers": markers,
            "fill": fill,
        }

        result = {"type": "plotly", "title": title, "fig": fig.to_dict(), "meta": meta}
        return result, meta

    def description_builder(_df: pd.DataFrame, _result_obj: Dict[str, Any], meta: Dict[str, Any]) -> str:
        parts = []
        parts.append(f"선 그래프(Line Plot)입니다. {meta['n_lines']}개의 선을 표시했습니다.")

        y_cols = meta.get("y_columns", [])
        if y_cols:
            parts.append(f"표시 컬럼: {', '.join(y_cols)}")

        trend = meta.get("trend")
        if trend and trend != "판단 불가":
            parts.append(f"전반적인 추세: {trend}")

        vol = meta.get("avg_volatility")
        if vol is not None:
            if vol > 0.5:
                parts.append("변동성이 큰 편입니다.")
            elif vol < 0.1:
                parts.append("변동성이 작고 안정적입니다.")
            else:
                parts.append("중간 정도의 변동성을 보입니다.")

        return " ".join(parts)

    return safe_run_tool(
        raw_args=args,
        core_fn=core_fn,
        title="line_plot",
        ext="json",
        description_builder=description_builder,
    )
