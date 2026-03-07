from __future__ import annotations

from typing import Any, Dict, Optional, Tuple, List
from dataclasses import dataclass

import numpy as np
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots

from ..utils.plot_io import safe_run_tool


@dataclass
class TreeNode:
    """의사결정 트리 노드."""
    feature_idx: Optional[int] = None
    threshold: Optional[float] = None
    left: Optional["TreeNode"] = None
    right: Optional["TreeNode"] = None
    value: Optional[Any] = None
    is_leaf: bool = False


def decision_tree(args: Dict[str, Any]) -> Dict[str, Any]:
    """의사결정 트리(Decision Tree) 분류 분석을 수행하고 결과를 시각화한다.

    분류 또는 회귀 문제에 사용할 수 있는 의사결정 트리 모델을 학습한다.
    트리 구조, 특성 중요도, 분류 성능 지표 등을 제공한다.

    데이터 입력 방식 (source_type으로 구분):
      1. artifact (권장):
         {
           "source_type": "artifact",
           "artifact_name": "iris.csv",
           "features": ["sepal_length", "sepal_width", "petal_length", "petal_width"],
           "target": "species"
         }

      2. file:
         {
           "source_type": "file",
           "path": "C:/data/iris.csv",
           "features": [...],
           "target": "species"
         }

      3. direct:
         {
           "source_type": "direct",
           "data": [...],
           "features": ["x1", "x2"],
           "target": "y"
         }

    모델 파라미터:
      - features (list[str], required): 독립변수(X) 컬럼명들
      - target (str, required): 종속변수(y) 컬럼명
      - test_size (float, default=0.2): 테스트 데이터 비율
      - max_depth (int, default=5): 트리 최대 깊이
      - min_samples_split (int, default=2): 분할에 필요한 최소 샘플 수
      - task (str, default="classification"): 작업 유형 (classification, regression)
      - title (str, optional): 결과 그래프 제목

    출력(JSON 파일 내용):
      {
        "type": "plotly",
        "title": "...",
        "fig": <plotly figure dict>,
        "meta": {
          "accuracy": float,  # 분류
          "mse": float,       # 회귀
          "feature_importance": {...},
          "tree_depth": int,
          ...
        }
      }
    """

    def _entropy(y: np.ndarray) -> float:
        """엔트로피 계산."""
        _, counts = np.unique(y, return_counts=True)
        probs = counts / len(y)
        return -np.sum(probs * np.log2(probs + 1e-10))

    def _gini(y: np.ndarray) -> float:
        """지니 불순도 계산."""
        _, counts = np.unique(y, return_counts=True)
        probs = counts / len(y)
        return 1 - np.sum(probs ** 2)

    def _mse(y: np.ndarray) -> float:
        """MSE 계산 (회귀)."""
        return np.var(y)

    def _best_split(X: np.ndarray, y: np.ndarray, task: str) -> Tuple[Optional[int], Optional[float]]:
        """최적 분할점 찾기."""
        n_samples, n_features = X.shape
        best_gain = -float("inf")
        best_feature = None
        best_threshold = None

        if task == "classification":
            parent_impurity = _gini(y)
        else:
            parent_impurity = _mse(y)

        for feature_idx in range(n_features):
            thresholds = np.unique(X[:, feature_idx])

            for threshold in thresholds:
                left_mask = X[:, feature_idx] <= threshold
                right_mask = ~left_mask

                if np.sum(left_mask) == 0 or np.sum(right_mask) == 0:
                    continue

                if task == "classification":
                    left_impurity = _gini(y[left_mask])
                    right_impurity = _gini(y[right_mask])
                else:
                    left_impurity = _mse(y[left_mask])
                    right_impurity = _mse(y[right_mask])

                n_left = np.sum(left_mask)
                n_right = np.sum(right_mask)
                weighted_impurity = (n_left * left_impurity + n_right * right_impurity) / n_samples
                gain = parent_impurity - weighted_impurity

                if gain > best_gain:
                    best_gain = gain
                    best_feature = feature_idx
                    best_threshold = threshold

        return best_feature, best_threshold

    def _build_tree(X: np.ndarray, y: np.ndarray, depth: int, max_depth: int, min_samples: int, task: str) -> TreeNode:
        """재귀적으로 트리 구축."""
        n_samples = len(y)

        # 종료 조건
        if depth >= max_depth or n_samples < min_samples or len(np.unique(y)) == 1:
            if task == "classification":
                values, counts = np.unique(y, return_counts=True)
                value = values[np.argmax(counts)]
            else:
                value = np.mean(y)
            return TreeNode(value=value, is_leaf=True)

        feature_idx, threshold = _best_split(X, y, task)

        if feature_idx is None:
            if task == "classification":
                values, counts = np.unique(y, return_counts=True)
                value = values[np.argmax(counts)]
            else:
                value = np.mean(y)
            return TreeNode(value=value, is_leaf=True)

        left_mask = X[:, feature_idx] <= threshold
        right_mask = ~left_mask

        left = _build_tree(X[left_mask], y[left_mask], depth + 1, max_depth, min_samples, task)
        right = _build_tree(X[right_mask], y[right_mask], depth + 1, max_depth, min_samples, task)

        return TreeNode(feature_idx=feature_idx, threshold=threshold, left=left, right=right)

    def _predict_one(x: np.ndarray, node: TreeNode) -> Any:
        """단일 샘플 예측."""
        if node.is_leaf:
            return node.value
        if x[node.feature_idx] <= node.threshold:
            return _predict_one(x, node.left)
        return _predict_one(x, node.right)

    def _predict(X: np.ndarray, tree: TreeNode) -> np.ndarray:
        """배치 예측."""
        return np.array([_predict_one(x, tree) for x in X])

    def _get_feature_importance(tree: TreeNode, n_features: int) -> np.ndarray:
        """특성 중요도 계산 (분할 횟수 기반)."""
        importance = np.zeros(n_features)

        def _traverse(node: TreeNode, weight: float):
            if node.is_leaf:
                return
            importance[node.feature_idx] += weight
            _traverse(node.left, weight * 0.5)
            _traverse(node.right, weight * 0.5)

        _traverse(tree, 1.0)
        if importance.sum() > 0:
            importance = importance / importance.sum()
        return importance

    def _tree_depth(node: TreeNode) -> int:
        """트리 깊이 계산."""
        if node.is_leaf:
            return 1
        return 1 + max(_tree_depth(node.left), _tree_depth(node.right))

    def _split_data(df: pd.DataFrame, test_size: float, random_state: int = 42) -> Tuple[pd.DataFrame, pd.DataFrame]:
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
            raise ValueError("target(종속변수 컬럼)을 지정해주세요.")

        if isinstance(features, str):
            features = [features]

        test_size = float(raw_args.get("test_size", 0.2))
        max_depth = int(raw_args.get("max_depth", 5))
        min_samples_split = int(raw_args.get("min_samples_split", 2))
        task = (raw_args.get("task") or "classification").lower()
        title = raw_args.get("title") or f"Decision Tree: {target}"

        # 데이터 준비
        use_cols = features + [target]
        d = df[use_cols].copy()

        for col in features:
            d[col] = pd.to_numeric(d[col], errors="coerce")

        d = d.dropna()

        if task == "classification":
            # 레이블 인코딩
            classes = d[target].unique()
            class_map = {c: i for i, c in enumerate(classes)}
            d["_target_encoded"] = d[target].map(class_map)
            target_col = "_target_encoded"
        else:
            d[target] = pd.to_numeric(d[target], errors="coerce")
            d = d.dropna()
            target_col = target

        if len(d) < 10:
            raise ValueError("유효한 데이터가 10개 미만입니다.")

        # 분리
        train_df, test_df = _split_data(d, test_size)

        X_train = train_df[features].to_numpy()
        y_train = train_df[target_col].to_numpy()
        X_test = test_df[features].to_numpy()
        y_test = test_df[target_col].to_numpy()

        # 트리 학습
        tree = _build_tree(X_train, y_train, 0, max_depth, min_samples_split, task)

        # 예측
        y_train_pred = _predict(X_train, tree)
        y_test_pred = _predict(X_test, tree)

        # 성능 계산
        if task == "classification":
            train_acc = np.mean(y_train == y_train_pred)
            test_acc = np.mean(y_test == y_test_pred)
            metrics = {"accuracy_train": float(train_acc), "accuracy_test": float(test_acc)}
        else:
            train_mse = np.mean((y_train - y_train_pred) ** 2)
            test_mse = np.mean((y_test - y_test_pred) ** 2)
            metrics = {"mse_train": float(train_mse), "mse_test": float(test_mse)}

        # 특성 중요도
        importance = _get_feature_importance(tree, len(features))
        depth = _tree_depth(tree)

        # 시각화
        fig = make_subplots(
            rows=1, cols=2,
            subplot_titles=("특성 중요도", "예측 vs 실제")
        )

        # 특성 중요도 바 차트
        sorted_idx = np.argsort(importance)[::-1]
        fig.add_trace(
            go.Bar(
                x=[features[i] for i in sorted_idx],
                y=[importance[i] for i in sorted_idx],
                name="중요도",
            ),
            row=1, col=1
        )

        # 예측 vs 실제
        if task == "classification":
            # 혼동 행렬 히트맵
            unique_classes = np.unique(np.concatenate([y_test, y_test_pred]))
            n_classes = len(unique_classes)
            cm = np.zeros((n_classes, n_classes), dtype=int)
            for true, pred in zip(y_test.astype(int), y_test_pred.astype(int)):
                cm[true, pred] += 1

            fig.add_trace(
                go.Heatmap(
                    z=cm,
                    x=[f"Pred {i}" for i in range(n_classes)],
                    y=[f"True {i}" for i in range(n_classes)],
                    colorscale="Blues",
                ),
                row=1, col=2
            )
        else:
            fig.add_trace(
                go.Scatter(x=y_test.tolist(), y=y_test_pred.tolist(), mode="markers", name="예측"),
                row=1, col=2
            )
            min_val = min(y_test.min(), y_test_pred.min())
            max_val = max(y_test.max(), y_test_pred.max())
            fig.add_trace(
                go.Scatter(x=[min_val, max_val], y=[min_val, max_val], mode="lines", line=dict(dash="dash"), name="완벽한 예측"),
                row=1, col=2
            )

        fig.update_layout(title=title, height=400, showlegend=False)

        feature_importance = {f: float(imp) for f, imp in zip(features, importance)}

        meta = {
            "features": features,
            "target": target,
            "task": task,
            "n_train": int(len(train_df)),
            "n_test": int(len(test_df)),
            "tree_depth": depth,
            "max_depth_setting": max_depth,
            "feature_importance": feature_importance,
            "most_important": features[np.argmax(importance)],
            **metrics,
        }

        if task == "classification":
            meta["n_classes"] = len(classes)
            meta["classes"] = list(classes)

        result = {"type": "plotly", "title": title, "fig": fig.to_dict(), "meta": meta}
        return result, meta

    def description_builder(_df: pd.DataFrame, _result_obj: Dict[str, Any], meta: Dict[str, Any]) -> str:
        parts = []
        parts.append(f"의사결정 트리 {'분류' if meta['task'] == 'classification' else '회귀'} 분석을 수행했습니다.")
        parts.append(f"트리 깊이: {meta['tree_depth']}")

        if meta["task"] == "classification":
            parts.append(f"테스트 정확도: {meta['accuracy_test']*100:.1f}%")
        else:
            parts.append(f"테스트 MSE: {meta['mse_test']:.4f}")

        parts.append(f"가장 중요한 특성: '{meta['most_important']}'")
        return " ".join(parts)

    return safe_run_tool(
        raw_args=args,
        core_fn=core_fn,
        title="decision_tree",
        ext="json",
        description_builder=description_builder,
    )
