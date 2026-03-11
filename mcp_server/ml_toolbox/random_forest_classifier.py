from __future__ import annotations

from typing import Any, Dict, Optional, Tuple, List
from collections import Counter

import numpy as np
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots

from ..utils.plot_io import safe_run_tool


def random_forest_classifier(args: Dict[str, Any]) -> Dict[str, Any]:
    """랜덤 포레스트 분류(Random Forest Classifier)를 수행하고 결과를 시각화한다.

    결정 트리 앙상블을 사용하여 분류 문제를 해결한다.
    특성 중요도, 혼동 행렬, 정확도 등 상세한 결과를 제공한다.

    Note: 이 구현은 scikit-learn 없이 순수 Python/NumPy로 구현된 간단한 버전이다.
    대규모 데이터나 프로덕션 환경에서는 scikit-learn 사용을 권장한다.

    데이터 입력 방식 (source_type으로 구분):
      1. artifact (권장) - ADK 아티팩트에서 로드:
         {
           "source_type": "artifact",
           "artifact_name": "iris",
           "columns": ["sepal_length", "sepal_width", "species"],
           "features": ["sepal_length", "sepal_width"],
           "target": "species"
         }

      2. file - 로컬 파일에서 로드:
         {
           "source_type": "file",
           "path": "C:/data/iris.csv",
           "features": ["sepal_length", "sepal_width"],
           "target": "species"
         }

      3. direct - 데이터 직접 전달:
         {
           "source_type": "direct",
           "data": [{"x1":1,"x2":2,"label":"A"}, ...],
           "features": ["x1", "x2"],
           "target": "label"
         }

      하위 호환 (기존 형식):
        - kind="direct" + data=[...]
        - kind="locator" + artifact_locator={...}

    모델 파라미터:
      - features (list[str], required): 독립변수(X) 컬럼명들
      - target (str, required): 종속변수(y, 분류 레이블) 컬럼명
      - n_trees (int, default=10): 트리 개수 (많을수록 안정적이나 느림)
      - max_depth (int, default=5): 각 트리의 최대 깊이
      - min_samples_split (int, default=5): 분할에 필요한 최소 샘플 수
      - test_size (float, default=0.2): 테스트 데이터 비율
      - title (str, optional): 결과 그래프 제목

    출력(JSON 파일 내용):
      {
        "type":"plotly",
        "title":"...",
        "fig": <plotly figure dict>,
        "meta": {
          "accuracy": float,
          "feature_importance": {feature: value, ...},
          "confusion_matrix": [[...], ...],
          "class_labels": [...],
          ...
        }
      }
    """

    class DecisionTreeNode:
        """간단한 결정 트리 노드."""
        def __init__(self):
            self.feature_idx = None
            self.threshold = None
            self.left = None
            self.right = None
            self.value = None  # 리프 노드의 예측 클래스

    def _gini_impurity(y: np.ndarray) -> float:
        """지니 불순도 계산."""
        if len(y) == 0:
            return 0.0
        _, counts = np.unique(y, return_counts=True)
        probs = counts / len(y)
        return 1.0 - np.sum(probs ** 2)

    def _best_split(X: np.ndarray, y: np.ndarray, feature_indices: List[int], min_samples: int) -> Tuple[Optional[int], Optional[float]]:
        """최적 분할점 찾기."""
        best_gini = float('inf')
        best_feature = None
        best_threshold = None

        for feat_idx in feature_indices:
            thresholds = np.unique(X[:, feat_idx])
            for thr in thresholds:
                left_mask = X[:, feat_idx] <= thr
                right_mask = ~left_mask

                if np.sum(left_mask) < min_samples or np.sum(right_mask) < min_samples:
                    continue

                left_gini = _gini_impurity(y[left_mask])
                right_gini = _gini_impurity(y[right_mask])

                n = len(y)
                weighted_gini = (np.sum(left_mask) * left_gini + np.sum(right_mask) * right_gini) / n

                if weighted_gini < best_gini:
                    best_gini = weighted_gini
                    best_feature = feat_idx
                    best_threshold = thr

        return best_feature, best_threshold

    def _build_tree(X: np.ndarray, y: np.ndarray, depth: int, max_depth: int, min_samples: int, n_features: int) -> DecisionTreeNode:
        """결정 트리 구축."""
        node = DecisionTreeNode()

        # 종료 조건
        if depth >= max_depth or len(y) < min_samples * 2 or len(np.unique(y)) == 1:
            # 다수결로 클래스 결정
            counts = Counter(y)
            node.value = counts.most_common(1)[0][0]
            return node

        # 랜덤하게 특성 선택
        n_total_features = X.shape[1]
        feature_indices = np.random.choice(n_total_features, size=min(n_features, n_total_features), replace=False).tolist()

        feat_idx, threshold = _best_split(X, y, feature_indices, min_samples)

        if feat_idx is None:
            counts = Counter(y)
            node.value = counts.most_common(1)[0][0]
            return node

        node.feature_idx = feat_idx
        node.threshold = threshold

        left_mask = X[:, feat_idx] <= threshold
        right_mask = ~left_mask

        node.left = _build_tree(X[left_mask], y[left_mask], depth + 1, max_depth, min_samples, n_features)
        node.right = _build_tree(X[right_mask], y[right_mask], depth + 1, max_depth, min_samples, n_features)

        return node

    def _predict_tree(node: DecisionTreeNode, x: np.ndarray) -> Any:
        """단일 트리로 예측."""
        if node.value is not None:
            return node.value
        if x[node.feature_idx] <= node.threshold:
            return _predict_tree(node.left, x)
        return _predict_tree(node.right, x)

    def _predict_forest(trees: List[DecisionTreeNode], X: np.ndarray) -> np.ndarray:
        """포레스트로 예측 (다수결)."""
        predictions = []
        for x in X:
            tree_preds = [_predict_tree(tree, x) for tree in trees]
            counts = Counter(tree_preds)
            predictions.append(counts.most_common(1)[0][0])
        return np.array(predictions)

    def _calculate_feature_importance(trees: List[DecisionTreeNode], n_features: int) -> np.ndarray:
        """특성 중요도 계산 (사용 빈도 기반)."""
        importance = np.zeros(n_features)

        def traverse(node: DecisionTreeNode, depth: int):
            if node.value is not None:
                return
            # 깊이가 얕을수록 더 중요
            weight = 1.0 / (depth + 1)
            importance[node.feature_idx] += weight
            traverse(node.left, depth + 1)
            traverse(node.right, depth + 1)

        for tree in trees:
            traverse(tree, 0)

        # 정규화
        total = importance.sum()
        if total > 0:
            importance = importance / total

        return importance

    def _confusion_matrix(y_true: np.ndarray, y_pred: np.ndarray, labels: List) -> np.ndarray:
        """혼동 행렬 계산."""
        n = len(labels)
        label_to_idx = {l: i for i, l in enumerate(labels)}
        matrix = np.zeros((n, n), dtype=int)
        for true, pred in zip(y_true, y_pred):
            if true in label_to_idx and pred in label_to_idx:
                matrix[label_to_idx[true], label_to_idx[pred]] += 1
        return matrix

    def _split_data(df: pd.DataFrame, test_size: float, random_state: int = 42) -> Tuple[pd.DataFrame, pd.DataFrame]:
        """학습/테스트 데이터 분리."""
        n = len(df)
        n_test = int(n * test_size)
        np.random.seed(random_state)
        indices = np.random.permutation(n)
        test_idx = indices[:n_test]
        train_idx = indices[n_test:]
        return df.iloc[train_idx].copy(), df.iloc[test_idx].copy()

    def core_fn(df: pd.DataFrame, columns: Optional[list], raw_args: Dict[str, Any]) -> Tuple[Dict[str, Any], Dict[str, Any]]:
        if df is None or df.empty:
            raise ValueError("입력 데이터가 비어있습니다.")

        features = raw_args.get("features")
        target = raw_args.get("target")

        if not features:
            raise ValueError("features(독립변수 컬럼들)를 지정해주세요.")
        if not target:
            raise ValueError("target(분류 레이블 컬럼)을 지정해주세요.")

        if isinstance(features, str):
            features = [features]

        # 컬럼 존재 확인
        missing_features = [f for f in features if f not in df.columns]
        if missing_features:
            raise ValueError(f"존재하지 않는 feature 컬럼: {missing_features}")
        if target not in df.columns:
            raise ValueError(f"존재하지 않는 target 컬럼: {target}")

        n_trees = int(raw_args.get("n_trees", 10))
        max_depth = int(raw_args.get("max_depth", 5))
        min_samples_split = int(raw_args.get("min_samples_split", 5))
        test_size = float(raw_args.get("test_size", 0.2))
        title = raw_args.get("title") or f"Random Forest: {', '.join(features[:3])}{'...' if len(features) > 3 else ''} → {target}"

        # 데이터 준비
        use_cols = features + [target]
        d = df[use_cols].copy()

        # 수치형 변환 (features만)
        for col in features:
            d[col] = pd.to_numeric(d[col], errors="coerce")

        # 결측치 제거
        d = d.dropna()

        if len(d) < 20:
            raise ValueError("유효한 데이터가 20개 미만입니다. 더 많은 데이터가 필요합니다.")

        # 클래스 레이블
        class_labels = sorted(d[target].unique().tolist())
        n_classes = len(class_labels)

        if n_classes < 2:
            raise ValueError("분류를 위해 최소 2개 이상의 클래스가 필요합니다.")

        # 학습/테스트 분리
        train_df, test_df = _split_data(d, test_size)

        X_train = train_df[features].to_numpy()
        y_train = train_df[target].to_numpy()
        X_test = test_df[features].to_numpy()
        y_test = test_df[target].to_numpy()

        # 랜덤 포레스트 학습
        n_features_per_tree = max(1, int(np.sqrt(len(features))))
        trees = []
        np.random.seed(42)

        for i in range(n_trees):
            # 부트스트랩 샘플링
            indices = np.random.choice(len(X_train), size=len(X_train), replace=True)
            X_boot = X_train[indices]
            y_boot = y_train[indices]

            tree = _build_tree(X_boot, y_boot, 0, max_depth, min_samples_split, n_features_per_tree)
            trees.append(tree)

        # 예측
        y_train_pred = _predict_forest(trees, X_train)
        y_test_pred = _predict_forest(trees, X_test)

        # 성능 지표
        train_accuracy = float(np.mean(y_train_pred == y_train))
        test_accuracy = float(np.mean(y_test_pred == y_test))

        # 특성 중요도
        importance = _calculate_feature_importance(trees, len(features))
        feature_importance = {f: float(imp) for f, imp in zip(features, importance)}

        # 혼동 행렬
        cm = _confusion_matrix(y_test, y_test_pred, class_labels)

        # 시각화 (2x1 또는 2x2)
        fig = make_subplots(
            rows=2, cols=2,
            subplot_titles=(
                "특성 중요도",
                "혼동 행렬 (테스트)",
                f"클래스별 정확도",
                "예측 분포"
            ),
            specs=[[{"type": "bar"}, {"type": "heatmap"}],
                   [{"type": "bar"}, {"type": "pie"}]]
        )

        # 1. 특성 중요도
        sorted_features = sorted(zip(features, importance), key=lambda x: x[1], reverse=True)
        fig.add_trace(
            go.Bar(
                x=[f[0] for f in sorted_features],
                y=[f[1] for f in sorted_features],
                name="중요도",
            ),
            row=1, col=1
        )

        # 2. 혼동 행렬
        fig.add_trace(
            go.Heatmap(
                z=cm.tolist(),
                x=[str(l) for l in class_labels],
                y=[str(l) for l in class_labels],
                colorscale="Blues",
                showscale=False,
                text=cm.tolist(),
                texttemplate="%{text}",
            ),
            row=1, col=2
        )

        # 3. 클래스별 정확도
        class_accuracies = []
        for i, label in enumerate(class_labels):
            if cm[i].sum() > 0:
                acc = cm[i, i] / cm[i].sum()
            else:
                acc = 0.0
            class_accuracies.append(acc)

        fig.add_trace(
            go.Bar(
                x=[str(l) for l in class_labels],
                y=class_accuracies,
                name="정확도",
            ),
            row=2, col=1
        )

        # 4. 예측 분포 (파이 차트)
        pred_counts = Counter(y_test_pred)
        fig.add_trace(
            go.Pie(
                labels=[str(l) for l in pred_counts.keys()],
                values=list(pred_counts.values()),
                name="예측 분포",
            ),
            row=2, col=2
        )

        fig.update_layout(
            title=title,
            height=700,
            showlegend=False,
        )

        # 가장 중요한 특성
        most_important = sorted_features[0][0] if sorted_features else None

        meta = {
            "features": features,
            "target": target,
            "n_classes": n_classes,
            "class_labels": class_labels,
            "n_trees": n_trees,
            "max_depth": max_depth,
            "n_train": int(len(train_df)),
            "n_test": int(len(test_df)),
            "accuracy_train": train_accuracy,
            "accuracy_test": test_accuracy,
            "feature_importance": feature_importance,
            "confusion_matrix": cm.tolist(),
            "most_important_feature": most_important,
        }

        result = {"type": "plotly", "title": title, "fig": fig.to_dict(), "meta": meta}
        return result, meta

    def description_builder(_df: pd.DataFrame, _result_obj: Dict[str, Any], meta: Dict[str, Any]) -> str:
        parts = []
        parts.append(f"랜덤 포레스트 분류를 수행했습니다. (트리 {meta['n_trees']}개)")
        parts.append(f"클래스 수: {meta['n_classes']}개 ({', '.join(str(l) for l in meta['class_labels'][:3])}{'...' if len(meta['class_labels']) > 3 else ''})")
        parts.append(f"학습 데이터: {meta['n_train']}개, 테스트 데이터: {meta['n_test']}개")

        acc = meta.get("accuracy_test", 0)
        parts.append(f"테스트 정확도: {acc*100:.1f}%")

        most_imp = meta.get("most_important_feature")
        if most_imp:
            imp_val = meta.get("feature_importance", {}).get(most_imp, 0)
            parts.append(f"가장 중요한 특성: '{most_imp}' (중요도: {imp_val:.3f})")

        return " ".join(parts)

    return safe_run_tool(
        raw_args=args,
        core_fn=core_fn,
        title="random_forest_classifier",
        ext="json",
        description_builder=description_builder,
    )
