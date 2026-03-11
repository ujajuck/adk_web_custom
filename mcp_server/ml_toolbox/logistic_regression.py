from __future__ import annotations

from typing import Any, Dict, Optional, Tuple, List

import numpy as np
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots

from ..utils.plot_io import safe_run_tool


def logistic_regression(args: Dict[str, Any]) -> Dict[str, Any]:
    """로지스틱 회귀(Logistic Regression) 분류 분석을 수행하고 결과를 시각화한다.

    이진 또는 다중 클래스 분류 문제에 사용할 수 있는 로지스틱 회귀 모델을 학습한다.
    정확도, 정밀도, 재현율, F1 점수 등 상세한 분류 지표를 제공한다.

    데이터 입력 방식 (source_type으로 구분):
      1. artifact (권장):
         {
           "source_type": "artifact",
           "artifact_name": "customers.csv",
           "features": ["age", "income", "tenure"],
           "target": "churn"
         }

      2. file:
         {
           "source_type": "file",
           "path": "C:/data/customers.csv",
           "features": ["age", "income"],
           "target": "churn"
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
      - target (str, required): 종속변수(y) 컬럼명 (범주형)
      - test_size (float, default=0.2): 테스트 데이터 비율
      - max_iter (int, default=100): 최대 반복 횟수
      - learning_rate (float, default=0.1): 학습률
      - title (str, optional): 결과 그래프 제목

    출력(JSON 파일 내용):
      {
        "type": "plotly",
        "title": "...",
        "fig": <plotly figure dict>,
        "meta": {
          "accuracy": float,
          "precision": float,
          "recall": float,
          "f1_score": float,
          "coefficients": {...},
          ...
        }
      }
    """

    def _sigmoid(z: np.ndarray) -> np.ndarray:
        """시그모이드 함수."""
        z = np.clip(z, -500, 500)
        return 1 / (1 + np.exp(-z))

    def _fit_logistic(X: np.ndarray, y: np.ndarray, lr: float, max_iter: int) -> Tuple[np.ndarray, float]:
        """경사하강법으로 로지스틱 회귀 학습."""
        n_samples, n_features = X.shape
        weights = np.zeros(n_features)
        bias = 0.0

        for _ in range(max_iter):
            linear = X @ weights + bias
            predictions = _sigmoid(linear)

            dw = (1 / n_samples) * (X.T @ (predictions - y))
            db = (1 / n_samples) * np.sum(predictions - y)

            weights -= lr * dw
            bias -= lr * db

        return weights, bias

    def _predict_proba(X: np.ndarray, weights: np.ndarray, bias: float) -> np.ndarray:
        """확률 예측."""
        linear = X @ weights + bias
        return _sigmoid(linear)

    def _calculate_metrics(y_true: np.ndarray, y_pred: np.ndarray) -> Dict[str, float]:
        """분류 성능 지표 계산."""
        tp = np.sum((y_true == 1) & (y_pred == 1))
        tn = np.sum((y_true == 0) & (y_pred == 0))
        fp = np.sum((y_true == 0) & (y_pred == 1))
        fn = np.sum((y_true == 1) & (y_pred == 0))

        accuracy = (tp + tn) / (tp + tn + fp + fn) if (tp + tn + fp + fn) > 0 else 0
        precision = tp / (tp + fp) if (tp + fp) > 0 else 0
        recall = tp / (tp + fn) if (tp + fn) > 0 else 0
        f1 = 2 * precision * recall / (precision + recall) if (precision + recall) > 0 else 0

        return {
            "accuracy": float(accuracy),
            "precision": float(precision),
            "recall": float(recall),
            "f1_score": float(f1),
            "tp": int(tp),
            "tn": int(tn),
            "fp": int(fp),
            "fn": int(fn),
        }

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
            raise ValueError("target(종속변수 컬럼)을 지정해주세요.")

        if isinstance(features, str):
            features = [features]

        test_size = float(raw_args.get("test_size", 0.2))
        max_iter = int(raw_args.get("max_iter", 100))
        learning_rate = float(raw_args.get("learning_rate", 0.1))
        title = raw_args.get("title") or f"Logistic Regression: {target}"

        # 데이터 준비
        use_cols = features + [target]
        d = df[use_cols].copy()

        # 수치형 변환
        for col in features:
            d[col] = pd.to_numeric(d[col], errors="coerce")

        # 타겟 이진화
        unique_classes = d[target].dropna().unique()
        if len(unique_classes) != 2:
            # 다중 클래스인 경우 첫 번째 클래스를 1로
            d[target] = (d[target] == unique_classes[0]).astype(int)
        else:
            d[target] = pd.Categorical(d[target]).codes

        d = d.dropna()

        if len(d) < 10:
            raise ValueError("유효한 데이터가 10개 미만입니다.")

        # 학습/테스트 분리
        train_df, test_df = _split_data(d, test_size)

        X_train = train_df[features].to_numpy()
        y_train = train_df[target].to_numpy()
        X_test = test_df[features].to_numpy()
        y_test = test_df[target].to_numpy()

        # 스케일링
        mean = X_train.mean(axis=0)
        std = X_train.std(axis=0) + 1e-10
        X_train = (X_train - mean) / std
        X_test = (X_test - mean) / std

        # 학습
        weights, bias = _fit_logistic(X_train, y_train, learning_rate, max_iter)

        # 예측
        y_train_proba = _predict_proba(X_train, weights, bias)
        y_test_proba = _predict_proba(X_test, weights, bias)
        y_train_pred = (y_train_proba >= 0.5).astype(int)
        y_test_pred = (y_test_proba >= 0.5).astype(int)

        # 성능 지표
        train_metrics = _calculate_metrics(y_train, y_train_pred)
        test_metrics = _calculate_metrics(y_test, y_test_pred)

        # 시각화
        fig = make_subplots(
            rows=2, cols=2,
            subplot_titles=(
                "혼동 행렬 (테스트)",
                "ROC 곡선",
                "특성 중요도 (계수)",
                "확률 분포"
            )
        )

        # 1. 혼동 행렬
        cm = [[test_metrics["tn"], test_metrics["fp"]],
              [test_metrics["fn"], test_metrics["tp"]]]
        fig.add_trace(
            go.Heatmap(
                z=cm,
                x=["Predicted 0", "Predicted 1"],
                y=["Actual 0", "Actual 1"],
                colorscale="Blues",
                text=[[str(v) for v in row] for row in cm],
                texttemplate="%{text}",
            ),
            row=1, col=1
        )

        # 2. ROC 곡선
        thresholds = np.linspace(0, 1, 100)
        tpr_list = []
        fpr_list = []
        for th in thresholds:
            pred = (y_test_proba >= th).astype(int)
            tp = np.sum((y_test == 1) & (pred == 1))
            fn = np.sum((y_test == 1) & (pred == 0))
            fp = np.sum((y_test == 0) & (pred == 1))
            tn = np.sum((y_test == 0) & (pred == 0))
            tpr = tp / (tp + fn) if (tp + fn) > 0 else 0
            fpr = fp / (fp + tn) if (fp + tn) > 0 else 0
            tpr_list.append(tpr)
            fpr_list.append(fpr)

        fig.add_trace(
            go.Scatter(x=fpr_list, y=tpr_list, mode="lines", name="ROC"),
            row=1, col=2
        )
        fig.add_trace(
            go.Scatter(x=[0, 1], y=[0, 1], mode="lines", line=dict(dash="dash", color="gray"), name="Random"),
            row=1, col=2
        )

        # 3. 계수
        fig.add_trace(
            go.Bar(x=features, y=weights.tolist(), name="계수"),
            row=2, col=1
        )

        # 4. 확률 분포
        fig.add_trace(
            go.Histogram(x=y_test_proba[y_test == 0].tolist(), name="Class 0", opacity=0.7, nbinsx=20),
            row=2, col=2
        )
        fig.add_trace(
            go.Histogram(x=y_test_proba[y_test == 1].tolist(), name="Class 1", opacity=0.7, nbinsx=20),
            row=2, col=2
        )

        fig.update_layout(title=title, height=700, showlegend=False)

        # AUC 계산 (간단 버전)
        auc = np.trapz(sorted(tpr_list), sorted(fpr_list))

        coefficients = {f: float(w) for f, w in zip(features, weights)}

        meta = {
            "features": features,
            "target": target,
            "n_train": int(len(train_df)),
            "n_test": int(len(test_df)),
            "coefficients": coefficients,
            "bias": float(bias),
            "accuracy_train": train_metrics["accuracy"],
            "accuracy_test": test_metrics["accuracy"],
            "precision": test_metrics["precision"],
            "recall": test_metrics["recall"],
            "f1_score": test_metrics["f1_score"],
            "auc": float(abs(auc)),
            "confusion_matrix": test_metrics,
        }

        result = {"type": "plotly", "title": title, "fig": fig.to_dict(), "meta": meta}
        return result, meta

    def description_builder(_df: pd.DataFrame, _result_obj: Dict[str, Any], meta: Dict[str, Any]) -> str:
        parts = []
        parts.append("로지스틱 회귀 분류 분석을 수행했습니다.")
        parts.append(f"학습: {meta['n_train']}개, 테스트: {meta['n_test']}개")
        parts.append(f"정확도: {meta['accuracy_test']*100:.1f}%")
        parts.append(f"F1 점수: {meta['f1_score']:.3f}")
        parts.append(f"AUC: {meta['auc']:.3f}")
        return " ".join(parts)

    return safe_run_tool(
        raw_args=args,
        core_fn=core_fn,
        title="logistic_regression",
        ext="json",
        description_builder=description_builder,
    )
