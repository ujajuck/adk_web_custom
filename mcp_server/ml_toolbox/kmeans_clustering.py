from __future__ import annotations

from typing import Any, Dict, Optional, Tuple, List

import numpy as np
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots

from ..utils.plot_io import safe_run_tool


def kmeans_clustering(args: Dict[str, Any]) -> Dict[str, Any]:
    """K-평균 클러스터링(K-Means Clustering)을 수행하고 결과를 시각화한다.

    비지도 학습으로 데이터를 K개의 그룹으로 분류한다.
    클러스터 중심, 실루엣 점수, 엘보우 분석 등 상세한 결과를 제공한다.

    데이터 입력 방식 (source_type으로 구분):
      1. artifact (권장) - ADK 아티팩트에서 로드:
         {
           "source_type": "artifact",
           "artifact_name": "customers",
           "columns": ["age", "income", "spending"],
           "features": ["age", "income", "spending"],
           "n_clusters": 4
         }

      2. file - 로컬 파일에서 로드:
         {
           "source_type": "file",
           "path": "C:/data/customers.csv",
           "features": ["age", "income", "spending"],
           "n_clusters": 3
         }

      3. direct - 데이터 직접 전달:
         {
           "source_type": "direct",
           "data": [{"x":1,"y":2}, {"x":3,"y":4}],
           "features": ["x", "y"],
           "n_clusters": 3
         }

      하위 호환 (기존 형식):
        - kind="direct" + data=[...]
        - kind="locator" + artifact_locator={...}

    모델 파라미터:
      - features (list[str], required): 클러스터링에 사용할 수치형 컬럼들
      - n_clusters (int, default=3): 클러스터 개수 (K)
      - max_iter (int, default=100): 최대 반복 횟수
      - n_init (int, default=10): 서로 다른 초기값으로 실행할 횟수
      - normalize (bool, default=True): 클러스터링 전 정규화 여부
      - elbow_range (list[int], optional): 엘보우 분석할 K 범위 [min, max]
      - title (str, optional): 결과 그래프 제목

    출력(JSON 파일 내용):
      {
        "type":"plotly",
        "title":"...",
        "fig": <plotly figure dict>,
        "meta": {
          "n_clusters": int,
          "cluster_sizes": [int, ...],
          "centroids": [[...], ...],
          "inertia": float,
          "silhouette_score": float,
          ...
        }
      }
    """

    def _normalize_data(X: np.ndarray) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
        """Z-Score 정규화. 평균, 표준편차 반환."""
        mean = np.mean(X, axis=0)
        std = np.std(X, axis=0)
        std[std == 0] = 1  # 0으로 나누기 방지
        X_norm = (X - mean) / std
        return X_norm, mean, std

    def _kmeans_single(X: np.ndarray, k: int, max_iter: int, seed: int) -> Tuple[np.ndarray, np.ndarray, float]:
        """단일 K-Means 실행."""
        np.random.seed(seed)
        n_samples = len(X)

        # 랜덤 초기화 (k-means++)
        centroids = [X[np.random.randint(n_samples)]]
        for _ in range(1, k):
            distances = np.array([min(np.sum((x - c) ** 2) for c in centroids) for x in X])
            probs = distances / distances.sum()
            new_centroid_idx = np.random.choice(n_samples, p=probs)
            centroids.append(X[new_centroid_idx])
        centroids = np.array(centroids)

        labels = np.zeros(n_samples, dtype=int)

        for _ in range(max_iter):
            # 할당 단계
            new_labels = np.array([np.argmin([np.sum((x - c) ** 2) for c in centroids]) for x in X])

            # 수렴 확인
            if np.array_equal(labels, new_labels):
                break
            labels = new_labels

            # 업데이트 단계
            for i in range(k):
                cluster_points = X[labels == i]
                if len(cluster_points) > 0:
                    centroids[i] = cluster_points.mean(axis=0)

        # Inertia (WCSS) 계산
        inertia = sum(np.sum((X[labels == i] - centroids[i]) ** 2) for i in range(k))

        return labels, centroids, float(inertia)

    def _kmeans(X: np.ndarray, k: int, max_iter: int, n_init: int) -> Tuple[np.ndarray, np.ndarray, float]:
        """여러 번 실행하여 최적 결과 선택."""
        best_inertia = float('inf')
        best_labels = None
        best_centroids = None

        for i in range(n_init):
            labels, centroids, inertia = _kmeans_single(X, k, max_iter, seed=42 + i)
            if inertia < best_inertia:
                best_inertia = inertia
                best_labels = labels
                best_centroids = centroids

        return best_labels, best_centroids, best_inertia

    def _silhouette_score(X: np.ndarray, labels: np.ndarray) -> float:
        """실루엣 점수 계산."""
        n_samples = len(X)
        unique_labels = np.unique(labels)

        if len(unique_labels) < 2:
            return 0.0

        silhouette_vals = []

        for i in range(n_samples):
            # a(i): 같은 클러스터 내 평균 거리
            same_cluster = X[labels == labels[i]]
            if len(same_cluster) > 1:
                a_i = np.mean([np.sqrt(np.sum((X[i] - x) ** 2)) for x in same_cluster if not np.array_equal(x, X[i])])
            else:
                a_i = 0.0

            # b(i): 가장 가까운 다른 클러스터와의 평균 거리
            b_i = float('inf')
            for label in unique_labels:
                if label != labels[i]:
                    other_cluster = X[labels == label]
                    if len(other_cluster) > 0:
                        avg_dist = np.mean([np.sqrt(np.sum((X[i] - x) ** 2)) for x in other_cluster])
                        b_i = min(b_i, avg_dist)

            if b_i == float('inf'):
                b_i = 0.0

            # 실루엣 값
            if max(a_i, b_i) > 0:
                s_i = (b_i - a_i) / max(a_i, b_i)
            else:
                s_i = 0.0

            silhouette_vals.append(s_i)

        return float(np.mean(silhouette_vals))

    def _elbow_analysis(X: np.ndarray, k_range: List[int], max_iter: int) -> List[Dict]:
        """엘보우 분석."""
        results = []
        for k in range(k_range[0], k_range[1] + 1):
            _, _, inertia = _kmeans(X, k, max_iter, n_init=3)  # 빠른 분석을 위해 n_init=3
            results.append({"k": k, "inertia": inertia})
        return results

    def core_fn(df: pd.DataFrame, columns: Optional[list], raw_args: Dict[str, Any]) -> Tuple[Dict[str, Any], Dict[str, Any]]:
        if df is None or df.empty:
            raise ValueError("입력 데이터가 비어있습니다.")

        features = raw_args.get("features")

        if not features:
            # columns에서 가져오거나 수치형 컬럼 자동 선택
            if columns:
                features = [c for c in columns if c in df.columns]
            else:
                features = df.select_dtypes(include=[np.number]).columns.tolist()

        if isinstance(features, str):
            features = [features]

        if len(features) < 2:
            raise ValueError("클러스터링을 위해 최소 2개 이상의 특성이 필요합니다.")

        # 컬럼 존재 확인
        missing_features = [f for f in features if f not in df.columns]
        if missing_features:
            raise ValueError(f"존재하지 않는 feature 컬럼: {missing_features}")

        n_clusters = int(raw_args.get("n_clusters", 3))
        max_iter = int(raw_args.get("max_iter", 100))
        n_init = int(raw_args.get("n_init", 10))
        normalize = bool(raw_args.get("normalize", True))
        elbow_range = raw_args.get("elbow_range")
        title = raw_args.get("title") or f"K-Means Clustering (K={n_clusters})"

        if n_clusters < 2:
            raise ValueError("n_clusters는 2 이상이어야 합니다.")

        # 데이터 준비
        d = df[features].copy()
        for col in features:
            d[col] = pd.to_numeric(d[col], errors="coerce")
        d = d.dropna()

        if len(d) < n_clusters * 3:
            raise ValueError(f"데이터가 너무 적습니다. 최소 {n_clusters * 3}개 이상의 데이터가 필요합니다.")

        X = d.to_numpy()

        # 정규화
        if normalize:
            X_norm, mean, std = _normalize_data(X)
        else:
            X_norm = X
            mean, std = None, None

        # K-Means 실행
        labels, centroids_norm, inertia = _kmeans(X_norm, n_clusters, max_iter, n_init)

        # 원래 스케일로 중심 변환
        if normalize:
            centroids = centroids_norm * std + mean
        else:
            centroids = centroids_norm

        # 실루엣 점수 (샘플링하여 계산)
        sample_size = min(500, len(X_norm))
        if len(X_norm) > sample_size:
            sample_idx = np.random.choice(len(X_norm), sample_size, replace=False)
            silhouette = _silhouette_score(X_norm[sample_idx], labels[sample_idx])
        else:
            silhouette = _silhouette_score(X_norm, labels)

        # 클러스터 크기
        cluster_sizes = [int(np.sum(labels == i)) for i in range(n_clusters)]

        # 엘보우 분석
        elbow_data = None
        if elbow_range:
            if isinstance(elbow_range, list) and len(elbow_range) == 2:
                elbow_data = _elbow_analysis(X_norm, elbow_range, max_iter)

        # 시각화
        n_features = len(features)

        if n_features == 2:
            # 2D 산점도
            fig = make_subplots(
                rows=1, cols=2 if elbow_data else 1,
                subplot_titles=["클러스터 시각화"] + (["엘보우 분석"] if elbow_data else []),
            )

            for i in range(n_clusters):
                mask = labels == i
                fig.add_trace(
                    go.Scatter(
                        x=X[mask, 0].tolist(),
                        y=X[mask, 1].tolist(),
                        mode="markers",
                        name=f"클러스터 {i}",
                        opacity=0.7,
                    ),
                    row=1, col=1
                )

            # 중심점
            fig.add_trace(
                go.Scatter(
                    x=centroids[:, 0].tolist(),
                    y=centroids[:, 1].tolist(),
                    mode="markers",
                    name="중심점",
                    marker=dict(symbol="x", size=15, color="black", line=dict(width=2)),
                ),
                row=1, col=1
            )

            fig.update_xaxes(title_text=features[0], row=1, col=1)
            fig.update_yaxes(title_text=features[1], row=1, col=1)

            if elbow_data:
                fig.add_trace(
                    go.Scatter(
                        x=[d["k"] for d in elbow_data],
                        y=[d["inertia"] for d in elbow_data],
                        mode="lines+markers",
                        name="Inertia",
                    ),
                    row=1, col=2
                )
                fig.update_xaxes(title_text="K (클러스터 수)", row=1, col=2)
                fig.update_yaxes(title_text="Inertia (WCSS)", row=1, col=2)

        else:
            # 다차원: 클러스터 크기 막대 + 특성별 분포 + 엘보우
            fig = make_subplots(
                rows=2, cols=2,
                subplot_titles=(
                    "클러스터 크기",
                    "특성별 클러스터 중심",
                    "처음 2개 특성으로 시각화",
                    "엘보우 분석" if elbow_data else "실루엣 점수"
                )
            )

            # 1. 클러스터 크기
            fig.add_trace(
                go.Bar(
                    x=[f"클러스터 {i}" for i in range(n_clusters)],
                    y=cluster_sizes,
                    name="크기",
                ),
                row=1, col=1
            )

            # 2. 특성별 중심 (히트맵)
            fig.add_trace(
                go.Heatmap(
                    z=centroids.T.tolist(),
                    x=[f"C{i}" for i in range(n_clusters)],
                    y=features,
                    colorscale="RdBu",
                    showscale=True,
                ),
                row=1, col=2
            )

            # 3. 2D 투영
            for i in range(n_clusters):
                mask = labels == i
                fig.add_trace(
                    go.Scatter(
                        x=X[mask, 0].tolist(),
                        y=X[mask, 1].tolist(),
                        mode="markers",
                        name=f"C{i}",
                        opacity=0.6,
                    ),
                    row=2, col=1
                )

            fig.update_xaxes(title_text=features[0], row=2, col=1)
            fig.update_yaxes(title_text=features[1], row=2, col=1)

            # 4. 엘보우 또는 실루엣
            if elbow_data:
                fig.add_trace(
                    go.Scatter(
                        x=[d["k"] for d in elbow_data],
                        y=[d["inertia"] for d in elbow_data],
                        mode="lines+markers",
                        name="Inertia",
                    ),
                    row=2, col=2
                )
            else:
                fig.add_trace(
                    go.Indicator(
                        mode="gauge+number",
                        value=silhouette,
                        title={"text": "실루엣 점수"},
                        gauge={"axis": {"range": [-1, 1]}, "bar": {"color": "darkblue"}},
                    ),
                    row=2, col=2
                )

        fig.update_layout(
            title=title,
            height=600 if n_features == 2 else 700,
            showlegend=True,
        )

        # 실루엣 점수 해석
        if silhouette >= 0.7:
            silhouette_interpretation = "매우 좋음"
        elif silhouette >= 0.5:
            silhouette_interpretation = "적절함"
        elif silhouette >= 0.25:
            silhouette_interpretation = "약한 구조"
        else:
            silhouette_interpretation = "구조 없음 또는 부적절한 K"

        meta = {
            "features": features,
            "n_clusters": n_clusters,
            "n_samples": int(len(X)),
            "cluster_sizes": cluster_sizes,
            "centroids": centroids.tolist(),
            "inertia": inertia,
            "silhouette_score": silhouette,
            "silhouette_interpretation": silhouette_interpretation,
            "normalized": normalize,
            "elbow_data": elbow_data,
        }

        result = {"type": "plotly", "title": title, "fig": fig.to_dict(), "meta": meta}
        return result, meta

    def description_builder(_df: pd.DataFrame, _result_obj: Dict[str, Any], meta: Dict[str, Any]) -> str:
        parts = []
        parts.append(f"K-평균 클러스터링을 수행했습니다. (K={meta['n_clusters']})")
        parts.append(f"총 {meta['n_samples']}개의 데이터를 {meta['n_clusters']}개 그룹으로 분류했습니다.")

        sizes = meta.get("cluster_sizes", [])
        if sizes:
            sizes_str = ", ".join([f"C{i}:{s}개" for i, s in enumerate(sizes)])
            parts.append(f"클러스터 크기: {sizes_str}")

        sil = meta.get("silhouette_score", 0)
        interp = meta.get("silhouette_interpretation", "")
        parts.append(f"실루엣 점수: {sil:.3f} ({interp})")

        return " ".join(parts)

    return safe_run_tool(
        raw_args=args,
        core_fn=core_fn,
        title="kmeans_clustering",
        ext="json",
        description_builder=description_builder,
    )
