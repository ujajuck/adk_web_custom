from __future__ import annotations

from typing import Any, Dict, Optional, Tuple

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import plotly.io as pio

from ..utils.plot_io import safe_run_tool


def heatmap(args: Dict[str, Any]) -> Dict[str, Any]:
    """히트맵(Plotly)을 '행렬' 입력으로만 그려 JSON으로 저장하고 resource_link로 반환한다.

    입력(공통):
      - direct(JSON matrix):
        {"kind":"direct","data":{"index":[...],"columns":[...],"values":[[...],...]}, "mode":"matrix"}
      - locator(CSV/JSON):
        {"kind":"locator","artifact_locator":{"artifact_name":"...","file_name":"corr.csv"}, "mode":"matrix"}

    파라미터:
      - mode: "matrix" 고정(권장)
      - title (str, optional)
      - top_k_pairs (int, default=8): description에 포함할 강한 관계 쌍 개수
      - abs_threshold (float, default=0.7): |value|가 이 값 이상인 관계를 “강함”으로 간주
      - show_diagonal (bool, default=False): 대각선 포함 여부(상관행렬이면 보통 제외)

    출력(JSON 파일 내용):
      { "type":"plotly", "title":"...", "fig":<plotly dict>, "meta":{...} }
    """

    def _matrix_from_direct(obj: Any) -> pd.DataFrame:
        # obj = {"index":[...],"columns":[...],"values":[[...],...]}
        if not isinstance(obj, dict):
            raise ValueError("direct data는 dict(matrix) 형태여야 합니다.")
        index = obj.get("index")
        cols = obj.get("columns")
        vals = obj.get("values")
        if not (isinstance(index, list) and isinstance(cols, list) and isinstance(vals, list)):
            raise ValueError("direct matrix는 index/columns/values를 포함해야 합니다.")
        df = pd.DataFrame(vals, index=index, columns=cols)
        return df

    def _coerce_matrix(df: pd.DataFrame) -> pd.DataFrame:
        mat = df.copy()
        for c in mat.columns:
            mat[c] = pd.to_numeric(mat[c], errors="coerce")
        return mat

    def _top_pairs(mat: pd.DataFrame, top_k: int, abs_th: float, show_diag: bool) -> Dict[str, Any]:
        # 강한 관계쌍만 뽑기
        arr = mat.to_numpy(dtype=float)
        n = arr.shape[0]
        pairs = []
        for i in range(n):
            for j in range(n):
                if not show_diag and i == j:
                    continue
                v = arr[i, j]
                if np.isnan(v):
                    continue
                if abs(v) >= abs_th:
                    pairs.append((mat.index[i], mat.columns[j], float(v)))
        # 절댓값 기준 내림차순
        pairs.sort(key=lambda x: abs(x[2]), reverse=True)
        return {
            "abs_threshold": abs_th,
            "pairs": pairs[:top_k],
            "count_over_threshold": len(pairs),
        }

    def core_fn(df: pd.DataFrame, _columns: Optional[list], raw_args: Dict[str, Any]) -> Tuple[Dict[str, Any], Dict[str, Any]]:
        mode = (raw_args.get("mode") or "matrix").strip().lower()
        if mode != "matrix":
            raise ValueError("heatmap은 mode='matrix'만 지원하도록 분리했습니다.")

        title = raw_args.get("title") or "Heatmap"
        top_k = int(raw_args.get("top_k_pairs", 8))
        abs_th = float(raw_args.get("abs_threshold", 0.7))
        show_diag = bool(raw_args.get("show_diagonal", False))

        mat = df.copy()
        if mat.shape[1] >= 2:
            # 첫 컬럼이 문자열 라벨이고 나머지가 수치면 index 후보 raw_args로 index_col_name 받는게 맞을까
            first = mat.columns[0]
            if first not in mat.index and mat[first].dtype == object:
                # index 중복/결측 방지 최소 처리
                mat = mat.set_index(first)

        mat = _coerce_matrix(mat)

        if mat.shape[0] < 2 or mat.shape[1] < 2:
            raise ValueError("heatmap matrix는 최소 2x2 이상이어야 합니다.")

        fig = go.Figure(
            data=go.Heatmap(
                z=mat.to_numpy(dtype=float).tolist(),
                x=[str(c) for c in mat.columns.tolist()],
                y=[str(i) for i in mat.index.tolist()],
            )
        )
        fig.update_layout(title=title, xaxis_title="columns", yaxis_title="index")

        pairs_info = _top_pairs(mat, top_k=top_k, abs_th=abs_th, show_diag=show_diag)

        meta = {
            "mode": "matrix",
            "rows": int(mat.shape[0]),
            "cols": int(mat.shape[1]),
            "top_pairs": pairs_info,
        }

        json_obj = {"type": "plotly", "title": title, "fig": fig.to_dict(), "meta": meta}
        html_bytes = fig.to_html(include_plotlyjs="inline", full_html=True).encode("utf-8")
        png_bytes = None
        try:
            png_bytes = pio.to_image(fig, format="png")  
        except Exception:
            png_bytes = None 

        payloads: Dict[str, Any] = {"json": json_obj, "html": html_bytes}
        if png_bytes:
            payloads["png"] = png_bytes
        return payloads, meta


    def description_builder(_df: pd.DataFrame, _result_obj: Dict[str, Any], meta: Dict[str, Any]) -> str:
        info = meta.get("top_pairs", {})
        pairs = info.get("pairs", [])
        abs_th = info.get("abs_threshold")
        cnt = info.get("count_over_threshold", 0)

        if not pairs:
            return (
                f"히트맵(Plotly)입니다. |값| ≥ {abs_th:.2f}인 강한 관계쌍이 발견되지 않았습니다 "
                f"(matrix {meta.get('rows')}x{meta.get('cols')})."
            )

        bullets = []
        for a, b, v in pairs:
            sign = "양(+)의 관계" if v >= 0 else "음(-)의 관계"
            bullets.append(f"{a} ↔ {b}: {v:.3f} ({sign})")

        joined = "; ".join(bullets)
        return (
            f"히트맵(Plotly)입니다. |값| ≥ {abs_th:.2f}인 관계가 총 {cnt}개이며, "
            f"그 중 강한 관계(상위 {len(pairs)}개)는 {joined} 입니다."
        )

    return safe_run_tool(
        raw_args=args,
        core_fn=core_fn,
        title="heatmap",
        ext="json", # 하위호환용(멀티 payloads면 ext는 사실상 무시)
        description_builder=description_builder,
    )
