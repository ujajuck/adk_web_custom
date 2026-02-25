from __future__ import annotations

from typing import Any, Dict, Optional, Tuple

import numpy as np
import pandas as pd
import plotly.graph_objects as go

from ..utils.plot_io import safe_run_tool


def pie_chart(args: Dict[str, Any]) -> Dict[str, Any]:
    """파이 차트(Pie Chart) 또는 도넛 차트를 생성해 JSON으로 저장하고 resource_link로 반환한다.

    범주별 비율/구성을 시각화하는 데 적합하다.
    상위 N개 항목만 표시하고 나머지는 "기타"로 묶을 수 있다.

    입력 예시:
      - direct:
        {"kind":"direct","data":[{"category":"A","value":30},{"category":"B","value":70}],"labels":"category","values":"value"}
      - locator(LLM이 채우는 필드: artifact_name/file_name):
        {"kind":"locator","artifact_locator":{"artifact_name":"market_share","file_name":"market.csv"},"labels":"company","values":"share"}

    파라미터:
      - labels (str, required): 범주/라벨 컬럼명
      - values (str, optional): 값 컬럼명. 없으면 각 범주의 빈도(count)를 사용
      - agg (str, default="sum"): values 집계 방법 (sum|mean|count)
      - top_k (int, default=10): 표시할 상위 N개 항목
      - other_label (str, default="기타"): 나머지를 묶을 라벨
      - donut (bool, default=False): 도넛 차트 여부 (중앙에 구멍)
      - show_percent (bool, default=True): 퍼센트 표시
      - title (str, optional): 그래프 제목
      - null_label (str, default="null"): 결측 범주 라벨

    출력(JSON 파일 내용):
      {
        "type":"plotly",
        "title":"...",
        "fig": <plotly figure dict>,
        "meta": {
          "n_categories": int,
          "top1": {"label": str, "share": float},
          "concentration": str,  # "집중됨"|"분산됨"
          ...
        }
      }
    """

    def _pick_labels_column(df: pd.DataFrame, raw_args: Dict[str, Any], columns: Optional[list]) -> str:
        """라벨 컬럼 선택."""
        labels = raw_args.get("labels")
        if isinstance(labels, str) and labels in df.columns:
            return labels
        if columns and len(columns) >= 1 and columns[0] in df.columns:
            return columns[0]
        # 첫 번째 문자열/범주형 컬럼 자동 선택
        for col in df.columns:
            if df[col].dtype == "object" or str(df[col].dtype).startswith("category"):
                return col
        return df.columns[0]

    def _pick_values_column(df: pd.DataFrame, raw_args: Dict[str, Any], columns: Optional[list]) -> Optional[str]:
        """값 컬럼 선택."""
        values = raw_args.get("values")
        if isinstance(values, str) and values in df.columns:
            return values
        if columns and len(columns) >= 2 and columns[1] in df.columns:
            return columns[1]
        return None

    def _concentration_analysis(shares: np.ndarray) -> Dict[str, Any]:
        """비율 집중도 분석."""
        if len(shares) == 0:
            return {"hhi": None, "concentration": "판단 불가", "top3_share": None}

        # Herfindahl-Hirschman Index (HHI)
        hhi = float(np.sum(shares ** 2))

        # 상위 3개 점유율
        top3_share = float(np.sum(np.sort(shares)[-3:])) if len(shares) >= 3 else float(np.sum(shares))

        # 집중도 판단
        if hhi > 0.25 or top3_share > 0.8:
            concentration = "매우 집중됨"
        elif hhi > 0.15 or top3_share > 0.6:
            concentration = "집중됨"
        elif hhi > 0.1:
            concentration = "중간"
        else:
            concentration = "분산됨"

        return {
            "hhi": hhi,
            "concentration": concentration,
            "top3_share": top3_share,
        }

    def core_fn(df: pd.DataFrame, columns: Optional[list], raw_args: Dict[str, Any]) -> Tuple[Dict[str, Any], Dict[str, Any]]:
        if df is None or df.empty:
            raise ValueError("입력 데이터가 비어있습니다.")

        labels_col = _pick_labels_column(df, raw_args, columns)
        values_col = _pick_values_column(df, raw_args, columns)

        agg_method = (raw_args.get("agg") or "sum").strip().lower()
        top_k = int(raw_args.get("top_k", 10))
        other_label = str(raw_args.get("other_label", "기타"))
        donut = bool(raw_args.get("donut", False))
        show_percent = bool(raw_args.get("show_percent", True))
        null_label = str(raw_args.get("null_label", "null"))

        title_suffix = f" ({values_col})" if values_col else " (빈도)"
        title = raw_args.get("title") or f"Pie Chart: {labels_col}{title_suffix}"

        if top_k <= 0:
            raise ValueError("top_k는 1 이상의 정수여야 합니다.")

        # 데이터 준비
        d = df[[labels_col]].copy() if not values_col else df[[labels_col, values_col]].copy()
        d[labels_col] = d[labels_col].astype("string").fillna(null_label)

        if values_col:
            d[values_col] = pd.to_numeric(d[values_col], errors="coerce")

            # 집계
            agg_funcs = {"sum": "sum", "mean": "mean", "count": "count"}
            agg_fn = agg_funcs.get(agg_method, "sum")
            grouped = d.groupby(labels_col, dropna=False)[values_col].agg(agg_fn).reset_index()
            grouped.columns = ["label", "value"]
        else:
            # 빈도 계산
            grouped = d[labels_col].value_counts().reset_index()
            grouped.columns = ["label", "value"]

        # 정렬 후 상위 K개
        grouped = grouped.sort_values("value", ascending=False)

        if len(grouped) > top_k:
            top_data = grouped.head(top_k).copy()
            others_sum = grouped.iloc[top_k:]["value"].sum()
            if others_sum > 0:
                others_row = pd.DataFrame([{"label": other_label, "value": others_sum}])
                top_data = pd.concat([top_data, others_row], ignore_index=True)
            grouped = top_data

        labels = grouped["label"].tolist()
        values = grouped["value"].to_numpy().astype(float)

        total = np.sum(values)
        if total <= 0:
            raise ValueError("값의 합이 0 이하입니다. 유효한 데이터가 필요합니다.")

        shares = values / total

        # 집중도 분석
        conc = _concentration_analysis(shares)

        # Plotly 파이 차트
        fig = go.Figure(data=[go.Pie(
            labels=labels,
            values=values.tolist(),
            hole=0.4 if donut else 0,
            textinfo="percent+label" if show_percent else "label",
            textposition="inside" if len(labels) <= 8 else "auto",
        )])

        fig.update_layout(title=title)

        # 상위 항목 정보
        top1 = {"label": labels[0], "value": float(values[0]), "share": float(shares[0])} if labels else None
        top2 = {"label": labels[1], "value": float(values[1]), "share": float(shares[1])} if len(labels) > 1 else None

        meta = {
            "labels_column": labels_col,
            "values_column": values_col,
            "agg": agg_method if values_col else "count",
            "n_categories": len(labels),
            "total": float(total),
            "top_k": top_k,
            "donut": donut,
            "top1": top1,
            "top2": top2,
            "hhi": conc["hhi"],
            "top3_share": conc["top3_share"],
            "concentration": conc["concentration"],
        }

        result = {"type": "plotly", "title": title, "fig": fig.to_dict(), "meta": meta}
        return result, meta

    def description_builder(_df: pd.DataFrame, _result_obj: Dict[str, Any], meta: Dict[str, Any]) -> str:
        parts = []
        chart_type = "도넛 차트" if meta.get("donut") else "파이 차트"
        parts.append(f"{chart_type}입니다. {meta['n_categories']}개의 범주를 표시했습니다.")

        top1 = meta.get("top1")
        if top1:
            parts.append(f"가장 큰 항목은 '{top1['label']}'으로 전체의 {top1['share']*100:.1f}%를 차지합니다.")

        top3_share = meta.get("top3_share")
        if top3_share is not None:
            parts.append(f"상위 3개 항목이 전체의 {top3_share*100:.1f}%를 차지합니다.")

        concentration = meta.get("concentration")
        if concentration:
            if concentration in ("매우 집중됨", "집중됨"):
                parts.append(f"구성이 {concentration} 패턴입니다. 소수 항목이 대부분을 차지합니다.")
            elif concentration == "분산됨":
                parts.append(f"구성이 비교적 {concentration} 패턴입니다. 여러 항목이 골고루 분포합니다.")

        return " ".join(parts)

    return safe_run_tool(
        raw_args=args,
        core_fn=core_fn,
        title="pie_chart",
        ext="json",
        description_builder=description_builder,
    )
