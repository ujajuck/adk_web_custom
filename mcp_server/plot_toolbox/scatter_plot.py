from __future__ import annotations

from typing import Any, Dict, Optional, Tuple

import numpy as np
import pandas as pd
import plotly.graph_objects as go

from ..utils.plot_io import safe_run_tool


def scatter_plot(args: Dict[str, Any]) -> Dict[str, Any]:
    """산점도(Scatter Plot)를 생성해 JSON으로 저장하고 resource_link로 반환한다.

    두 수치형 변수 간의 관계를 시각화한다.
    상관계수와 추세를 자동으로 분석하여 메타데이터에 포함한다.

    데이터 입력 방식 (source_type으로 구분):
      1. artifact (권장) - ADK 아티팩트에서 로드:
         {
           "source_type": "artifact",
           "artifact_name": "sales_data",
           "columns": ["price", "quantity"],
           "x": "price",
           "y": "quantity"
         }

      2. file - 로컬 파일에서 로드:
         {
           "source_type": "file",
           "path": "C:/data/sales.csv",
           "x": "price",
           "y": "quantity"
         }

      3. direct - 데이터 직접 전달:
         {
           "source_type": "direct",
           "data": [{"x":1,"y":2}, {"x":2,"y":4}],
           "x": "x",
           "y": "y"
         }

      하위 호환 (기존 형식):
        - kind="direct" + data=[...]
        - kind="locator" + artifact_locator={...}

    그래프 파라미터:
      - x (str, required): x축 컬럼명 (수치형)
      - y (str, required): y축 컬럼명 (수치형)
      - color (str, optional): 점 색상을 구분할 범주형 컬럼
      - size (str, optional): 점 크기를 결정할 수치형 컬럼
      - trendline (bool, default=False): 회귀 추세선 표시 여부
      - title (str, optional): 그래프 제목
      - opacity (float, default=0.7): 점 투명도 (0~1)
      - max_points (int, default=5000): 표시할 최대 점 개수 (샘플링)

    출력(JSON 파일 내용):
      {
        "type":"plotly",
        "title":"...",
        "fig": <plotly figure dict>,
        "meta": {
          "correlation": float,     # 피어슨 상관계수
          "correlation_strength": str,  # "강한 양의 상관" 등
          "n_points": int,
          ...
        }
      }
    """

    def _pick_column(df: pd.DataFrame, raw_args: Dict[str, Any], key: str, columns: Optional[list]) -> Optional[str]:
        """파라미터에서 컬럼명 추출."""
        c = raw_args.get(key)
        if isinstance(c, str) and c in df.columns:
            return c
        # columns 리스트에서 순서대로 x, y 매핑 시도
        if columns and key == "x" and len(columns) >= 1 and columns[0] in df.columns:
            return columns[0]
        if columns and key == "y" and len(columns) >= 2 and columns[1] in df.columns:
            return columns[1]
        return None

    def _correlation_strength(r: float) -> str:
        """상관계수 해석."""
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

    def _add_trendline(fig: go.Figure, x: np.ndarray, y: np.ndarray) -> Tuple[float, float]:
        """선형 회귀 추세선 추가. (기울기, 절편) 반환."""
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

    def core_fn(df: pd.DataFrame, columns: Optional[list], raw_args: Dict[str, Any]) -> Tuple[Dict[str, Any], Dict[str, Any]]:
        if df is None or df.empty:
            raise ValueError("입력 데이터가 비어있습니다.")

        x_col = _pick_column(df, raw_args, "x", columns)
        y_col = _pick_column(df, raw_args, "y", columns)

        if not x_col:
            raise ValueError("x 컬럼을 지정해주세요.")
        if not y_col:
            raise ValueError("y 컬럼을 지정해주세요.")

        color_col = raw_args.get("color")
        size_col = raw_args.get("size")
        trendline = bool(raw_args.get("trendline", False))
        opacity = float(raw_args.get("opacity", 0.7))
        max_points = int(raw_args.get("max_points", 5000))
        title = raw_args.get("title") or f"Scatter Plot: {x_col} vs {y_col}"

        # 데이터 준비
        use_cols = [x_col, y_col]
        if color_col and color_col in df.columns:
            use_cols.append(color_col)
        if size_col and size_col in df.columns:
            use_cols.append(size_col)

        d = df[use_cols].copy()

        # 수치형 변환
        d[x_col] = pd.to_numeric(d[x_col], errors="coerce")
        d[y_col] = pd.to_numeric(d[y_col], errors="coerce")

        # 결측치 제거
        d = d.dropna(subset=[x_col, y_col])

        n_original = len(d)

        # 샘플링
        if len(d) > max_points:
            d = d.sample(n=max_points, random_state=42)

        n_points = len(d)

        if n_points == 0:
            raise ValueError("유효한 데이터 포인트가 없습니다.")

        # 상관계수 계산
        x_vals = d[x_col].to_numpy()
        y_vals = d[y_col].to_numpy()

        correlation = float(np.corrcoef(x_vals, y_vals)[0, 1]) if n_points >= 2 else None
        correlation_strength = _correlation_strength(correlation) if correlation is not None else None

        # Plotly 그래프 생성
        fig = go.Figure()

        if color_col and color_col in d.columns:
            # 색상별로 분리
            for cat in d[color_col].dropna().unique():
                mask = d[color_col] == cat
                scatter_kwargs = dict(
                    x=d.loc[mask, x_col].tolist(),
                    y=d.loc[mask, y_col].tolist(),
                    mode="markers",
                    name=str(cat),
                    opacity=opacity,
                )
                if size_col and size_col in d.columns:
                    sizes = pd.to_numeric(d.loc[mask, size_col], errors="coerce").fillna(10)
                    # 크기 정규화 (5~50)
                    size_min, size_max = sizes.min(), sizes.max()
                    if size_max > size_min:
                        normalized = 5 + 45 * (sizes - size_min) / (size_max - size_min)
                    else:
                        normalized = 15
                    scatter_kwargs["marker"] = dict(size=normalized.tolist())
                fig.add_trace(go.Scatter(**scatter_kwargs))
        else:
            scatter_kwargs = dict(
                x=d[x_col].tolist(),
                y=d[y_col].tolist(),
                mode="markers",
                name="데이터",
                opacity=opacity,
            )
            if size_col and size_col in d.columns:
                sizes = pd.to_numeric(d[size_col], errors="coerce").fillna(10)
                size_min, size_max = sizes.min(), sizes.max()
                if size_max > size_min:
                    normalized = 5 + 45 * (sizes - size_min) / (size_max - size_min)
                else:
                    normalized = 15
                scatter_kwargs["marker"] = dict(size=normalized.tolist())
            fig.add_trace(go.Scatter(**scatter_kwargs))

        # 추세선
        slope, intercept = None, None
        if trendline:
            slope, intercept = _add_trendline(fig, x_vals, y_vals)

        fig.update_layout(
            title=title,
            xaxis_title=x_col,
            yaxis_title=y_col,
        )

        meta = {
            "x": x_col,
            "y": y_col,
            "color": color_col,
            "size": size_col,
            "n_original": n_original,
            "n_points": n_points,
            "sampled": n_original > max_points,
            "correlation": correlation,
            "correlation_strength": correlation_strength,
            "trendline": trendline,
            "slope": slope,
            "intercept": intercept,
        }

        result = {"type": "plotly", "title": title, "fig": fig.to_dict(), "meta": meta}
        return result, meta

    def description_builder(_df: pd.DataFrame, _result_obj: Dict[str, Any], meta: Dict[str, Any]) -> str:
        parts = []
        parts.append(f"산점도(Scatter Plot)입니다. {meta['n_points']}개의 점을 표시했습니다.")

        if meta.get("sampled"):
            parts.append(f"(원본 {meta['n_original']}개에서 샘플링)")

        corr = meta.get("correlation")
        strength = meta.get("correlation_strength")
        if corr is not None and strength:
            parts.append(f"상관계수는 {corr:.3f}로, {strength} 관계입니다.")

        if meta.get("trendline") and meta.get("slope") is not None:
            slope = meta["slope"]
            if abs(slope) > 0.001:
                direction = "증가" if slope > 0 else "감소"
                parts.append(f"추세선 기울기: {slope:.4f} ({direction} 추세)")

        return " ".join(parts)

    return safe_run_tool(
        raw_args=args,
        core_fn=core_fn,
        title="scatter_plot",
        ext="json",
        description_builder=description_builder,
    )
