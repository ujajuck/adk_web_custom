from __future__ import annotations

from typing import Any, Dict, Optional, Tuple, List

import numpy as np
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots

from ..utils.plot_io import safe_run_tool


def pca(args: Dict[str, Any]) -> Dict[str, Any]:
    """주성분 분석(PCA)을 수행하여 차원 축소 및 데이터 시각화를 제공한다.

    고차원 데이터를 저차원으로 변환하여 시각화하거나 특성의 중요도를 파악한다.
    설명된 분산, 주성분 로딩, 2D/3D 시각화 등을 제공한다.

    데이터 입력 방식 (source_type으로 구분):
      1. artifact (권장):
         {
           "source_type": "artifact",
           "artifact_name": "features.csv",
           "columns": ["x1", "x2", "x3", "x4"],
           "n_components": 2
         }

      2. file:
         {
           "source_type": "file",
           "path": "C:/data/features.csv",
           "n_components": 3
         }

      3. direct:
         {
           "source_type": "direct",
           "data": [...],
           "columns": ["x1", "x2", "x3"],
           "n_components": 2
         }

    분석 파라미터:
      - columns (list[str], optional): PCA를 적용할 컬럼들. 없으면 전체 수치형 컬럼
      - n_components (int, default=2): 추출할 주성분 수
      - color_by (str, optional): 시각화 시 색상을 구분할 범주형 컬럼
      - scale (bool, default=True): 데이터 표준화 여부
      - title (str, optional): 그래프 제목

    출력(JSON 파일 내용):
      {
        "type": "plotly",
        "title": "...",
        "fig": <plotly figure dict>,
        "meta": {
          "explained_variance_ratio": [...],
          "cumulative_variance": float,
          "components": [[...], ...],
          "feature_loadings": {...},
          ...
        }
      }
    """

    def _standardize(X: np.ndarray) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
        """데이터 표준화."""
        mean = X.mean(axis=0)
        std = X.std(axis=0) + 1e-10
        return (X - mean) / std, mean, std

    def _pca(X: np.ndarray, n_components: int) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
        """PCA 수행."""
        # 공분산 행렬
        cov_matrix = np.cov(X.T)

        # 고유값 분해
        eigenvalues, eigenvectors = np.linalg.eigh(cov_matrix)

        # 내림차순 정렬
        sorted_idx = np.argsort(eigenvalues)[::-1]
        eigenvalues = eigenvalues[sorted_idx]
        eigenvectors = eigenvectors[:, sorted_idx]

        # 설명된 분산 비율
        total_var = np.sum(eigenvalues)
        explained_variance_ratio = eigenvalues / total_var

        # 주성분 선택
        components = eigenvectors[:, :n_components].T
        explained_variance_ratio = explained_variance_ratio[:n_components]

        # 변환
        X_pca = X @ components.T

        return X_pca, components, explained_variance_ratio

    def core_fn(df: pd.DataFrame, columns: Optional[list], raw_args: Dict[str, Any]) -> Tuple[Dict[str, Any], Dict[str, Any]]:
        if df is None or df.empty:
            raise ValueError("입력 데이터가 비어있습니다.")

        n_components = int(raw_args.get("n_components", 2))
        color_by = raw_args.get("color_by")
        scale = bool(raw_args.get("scale", True))
        title = raw_args.get("title") or "PCA Analysis"

        # 수치형 컬럼 선택
        numeric_cols = df.select_dtypes(include=[np.number]).columns.tolist()
        target_cols = [c for c in (columns or numeric_cols) if c in numeric_cols]

        if len(target_cols) < 2:
            raise ValueError("PCA를 수행하려면 최소 2개의 수치형 컬럼이 필요합니다.")

        n_components = min(n_components, len(target_cols))

        # 데이터 준비
        X = df[target_cols].dropna().to_numpy()

        if len(X) < 10:
            raise ValueError("유효한 데이터가 10개 미만입니다.")

        # 표준화
        if scale:
            X_scaled, mean, std = _standardize(X)
        else:
            X_scaled = X

        # PCA 수행
        X_pca, components, explained_variance_ratio = _pca(X_scaled, n_components)

        # 누적 설명 분산
        cumulative_variance = float(np.sum(explained_variance_ratio))

        # 특성 로딩 (각 원본 특성이 각 주성분에 기여하는 정도)
        feature_loadings = {}
        for i, col in enumerate(target_cols):
            feature_loadings[col] = {
                f"PC{j+1}": float(components[j, i])
                for j in range(n_components)
            }

        # 가장 중요한 특성 (PC1 기준)
        pc1_loadings = np.abs(components[0])
        most_important_idx = np.argmax(pc1_loadings)
        most_important_feature = target_cols[most_important_idx]

        # 시각화
        if n_components >= 3:
            fig = make_subplots(
                rows=1, cols=2,
                subplot_titles=("3D PCA 시각화", "설명된 분산"),
                specs=[[{"type": "scatter3d"}, {"type": "bar"}]]
            )

            # 색상
            if color_by and color_by in df.columns:
                color_data = df.loc[df[target_cols].dropna().index, color_by]
                colors = pd.Categorical(color_data).codes
            else:
                colors = None

            fig.add_trace(
                go.Scatter3d(
                    x=X_pca[:, 0].tolist(),
                    y=X_pca[:, 1].tolist(),
                    z=X_pca[:, 2].tolist(),
                    mode="markers",
                    marker=dict(
                        size=5,
                        color=colors.tolist() if colors is not None else "blue",
                        colorscale="Viridis",
                        opacity=0.7,
                    ),
                    name="데이터",
                ),
                row=1, col=1
            )

            fig.add_trace(
                go.Bar(
                    x=[f"PC{i+1}" for i in range(n_components)],
                    y=explained_variance_ratio.tolist(),
                    name="설명 분산",
                ),
                row=1, col=2
            )

        else:
            fig = make_subplots(
                rows=1, cols=2,
                subplot_titles=("2D PCA 시각화", "설명된 분산")
            )

            # 색상
            if color_by and color_by in df.columns:
                color_data = df.loc[df[target_cols].dropna().index, color_by]
                unique_colors = color_data.unique()
                for uc in unique_colors:
                    mask = color_data == uc
                    fig.add_trace(
                        go.Scatter(
                            x=X_pca[mask, 0].tolist(),
                            y=X_pca[mask, 1].tolist() if n_components > 1 else [0] * mask.sum(),
                            mode="markers",
                            name=str(uc),
                            opacity=0.7,
                        ),
                        row=1, col=1
                    )
            else:
                fig.add_trace(
                    go.Scatter(
                        x=X_pca[:, 0].tolist(),
                        y=X_pca[:, 1].tolist() if n_components > 1 else [0] * len(X_pca),
                        mode="markers",
                        name="데이터",
                        opacity=0.7,
                    ),
                    row=1, col=1
                )

            fig.add_trace(
                go.Bar(
                    x=[f"PC{i+1}" for i in range(n_components)],
                    y=explained_variance_ratio.tolist(),
                    name="설명 분산",
                ),
                row=1, col=2
            )

        fig.update_layout(
            title=title,
            height=500,
        )

        if n_components >= 2:
            fig.update_xaxes(title_text="PC1", row=1, col=1)
            fig.update_yaxes(title_text="PC2", row=1, col=1)

        meta = {
            "original_features": target_cols,
            "n_components": n_components,
            "n_samples": int(len(X)),
            "explained_variance_ratio": explained_variance_ratio.tolist(),
            "cumulative_variance": cumulative_variance,
            "components": components.tolist(),
            "feature_loadings": feature_loadings,
            "most_important_feature": most_important_feature,
            "scaled": scale,
        }

        result = {"type": "plotly", "title": title, "fig": fig.to_dict(), "meta": meta}
        return result, meta

    def description_builder(_df: pd.DataFrame, _result_obj: Dict[str, Any], meta: Dict[str, Any]) -> str:
        parts = []
        parts.append(f"PCA 분석을 수행했습니다.")
        parts.append(f"{len(meta['original_features'])}개 특성 → {meta['n_components']}개 주성분으로 축소")
        parts.append(f"누적 설명 분산: {meta['cumulative_variance']*100:.1f}%")
        parts.append(f"가장 중요한 특성: '{meta['most_important_feature']}'")
        return " ".join(parts)

    return safe_run_tool(
        raw_args=args,
        core_fn=core_fn,
        title="pca",
        ext="json",
        description_builder=description_builder,
    )
