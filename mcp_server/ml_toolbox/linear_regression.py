from __future__ import annotations

from typing import Any, Dict, Optional, Tuple, List

import numpy as np
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots

from ..utils.plot_io import safe_run_tool


def linear_regression(args: Dict[str, Any]) -> Dict[str, Any]:
    """선형 회귀(Linear Regression) 분석을 수행하고 결과를 시각화한다.

    하나 이상의 독립변수(X)로 종속변수(y)를 예측하는 선형 모델을 학습한다.
    회귀 계수, 결정계수(R²), 잔차 분석 등 상세한 결과를 제공한다.

    입력 예시:
      - direct:
        {"kind":"direct","data":[{"x1":1,"x2":2,"y":3},...],"features":["x1","x2"],"target":"y"}
      - locator(LLM이 채우는 필드: artifact_name/file_name):
        {"kind":"locator","artifact_locator":{"artifact_name":"housing","file_name":"housing.csv"},"features":["area","rooms"],"target":"price"}

    파라미터:
      - features (list[str], required): 독립변수(X) 컬럼명들
      - target (str, required): 종속변수(y) 컬럼명
      - test_size (float, default=0.2): 테스트 데이터 비율 (0~1)
      - include_intercept (bool, default=True): 절편 포함 여부
      - title (str, optional): 결과 그래프 제목

    출력(JSON 파일 내용):
      {
        "type":"plotly",
        "title":"...",
        "fig": <plotly figure dict>,
        "meta": {
          "coefficients": {feature: value, ...},
          "intercept": float,
          "r2_train": float,
          "r2_test": float,
          "mse": float,
          "mae": float,
          ...
        }
      }
    """

    def _split_data(df: pd.DataFrame, test_size: float, random_state: int = 42) -> Tuple[pd.DataFrame, pd.DataFrame]:
        """학습/테스트 데이터 분리."""
        n = len(df)
        n_test = int(n * test_size)
        np.random.seed(random_state)
        indices = np.random.permutation(n)
        test_idx = indices[:n_test]
        train_idx = indices[n_test:]
        return df.iloc[train_idx].copy(), df.iloc[test_idx].copy()

    def _fit_linear_regression(X: np.ndarray, y: np.ndarray, include_intercept: bool) -> Tuple[np.ndarray, float]:
        """최소제곱법으로 선형 회귀 계수 계산."""
        if include_intercept:
            X = np.column_stack([np.ones(len(X)), X])

        # (X^T X)^-1 X^T y
        try:
            coeffs = np.linalg.lstsq(X, y, rcond=None)[0]
        except np.linalg.LinAlgError:
            coeffs = np.zeros(X.shape[1])

        if include_intercept:
            intercept = coeffs[0]
            coeffs = coeffs[1:]
        else:
            intercept = 0.0

        return coeffs, intercept

    def _predict(X: np.ndarray, coeffs: np.ndarray, intercept: float) -> np.ndarray:
        """예측값 계산."""
        return X @ coeffs + intercept

    def _calculate_metrics(y_true: np.ndarray, y_pred: np.ndarray) -> Dict[str, float]:
        """회귀 성능 지표 계산."""
        residuals = y_true - y_pred
        ss_res = np.sum(residuals ** 2)
        ss_tot = np.sum((y_true - np.mean(y_true)) ** 2)

        r2 = 1 - (ss_res / ss_tot) if ss_tot > 0 else 0.0
        mse = np.mean(residuals ** 2)
        rmse = np.sqrt(mse)
        mae = np.mean(np.abs(residuals))

        return {
            "r2": float(r2),
            "mse": float(mse),
            "rmse": float(rmse),
            "mae": float(mae),
        }

    def _interpret_r2(r2: float) -> str:
        """R² 해석."""
        if r2 >= 0.9:
            return "매우 높은 설명력"
        elif r2 >= 0.7:
            return "높은 설명력"
        elif r2 >= 0.5:
            return "중간 정도의 설명력"
        elif r2 >= 0.3:
            return "낮은 설명력"
        else:
            return "매우 낮은 설명력"

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

        # 컬럼 존재 확인
        missing_features = [f for f in features if f not in df.columns]
        if missing_features:
            raise ValueError(f"존재하지 않는 feature 컬럼: {missing_features}")
        if target not in df.columns:
            raise ValueError(f"존재하지 않는 target 컬럼: {target}")

        test_size = float(raw_args.get("test_size", 0.2))
        include_intercept = bool(raw_args.get("include_intercept", True))
        title = raw_args.get("title") or f"Linear Regression: {', '.join(features)} → {target}"

        # 데이터 준비
        use_cols = features + [target]
        d = df[use_cols].copy()

        # 수치형 변환
        for col in use_cols:
            d[col] = pd.to_numeric(d[col], errors="coerce")

        # 결측치 제거
        d = d.dropna()

        if len(d) < 10:
            raise ValueError("유효한 데이터가 10개 미만입니다. 더 많은 데이터가 필요합니다.")

        # 학습/테스트 분리
        train_df, test_df = _split_data(d, test_size)

        X_train = train_df[features].to_numpy()
        y_train = train_df[target].to_numpy()
        X_test = test_df[features].to_numpy()
        y_test = test_df[target].to_numpy()

        # 회귀 학습
        coeffs, intercept = _fit_linear_regression(X_train, y_train, include_intercept)

        # 예측
        y_train_pred = _predict(X_train, coeffs, intercept)
        y_test_pred = _predict(X_test, coeffs, intercept)

        # 성능 지표
        train_metrics = _calculate_metrics(y_train, y_train_pred)
        test_metrics = _calculate_metrics(y_test, y_test_pred)

        # 시각화 (2x2 서브플롯)
        fig = make_subplots(
            rows=2, cols=2,
            subplot_titles=(
                "실제값 vs 예측값 (테스트)",
                "잔차 분포",
                "특성 중요도 (계수)",
                "잔차 vs 예측값"
            )
        )

        # 1. 실제 vs 예측
        fig.add_trace(
            go.Scatter(
                x=y_test.tolist(),
                y=y_test_pred.tolist(),
                mode="markers",
                name="테스트 데이터",
                opacity=0.6,
            ),
            row=1, col=1
        )
        # 대각선 (완벽한 예측선)
        min_val, max_val = min(y_test.min(), y_test_pred.min()), max(y_test.max(), y_test_pred.max())
        fig.add_trace(
            go.Scatter(
                x=[min_val, max_val],
                y=[min_val, max_val],
                mode="lines",
                name="완벽한 예측",
                line=dict(dash="dash", color="red"),
            ),
            row=1, col=1
        )

        # 2. 잔차 분포 (히스토그램)
        residuals = y_test - y_test_pred
        fig.add_trace(
            go.Histogram(x=residuals.tolist(), name="잔차", nbinsx=30),
            row=1, col=2
        )

        # 3. 계수 (특성 중요도)
        fig.add_trace(
            go.Bar(
                x=features,
                y=coeffs.tolist(),
                name="회귀 계수",
            ),
            row=2, col=1
        )

        # 4. 잔차 vs 예측값
        fig.add_trace(
            go.Scatter(
                x=y_test_pred.tolist(),
                y=residuals.tolist(),
                mode="markers",
                name="잔차",
                opacity=0.6,
            ),
            row=2, col=2
        )
        fig.add_hline(y=0, line_dash="dash", line_color="red", row=2, col=2)

        fig.update_layout(
            title=title,
            height=700,
            showlegend=False,
        )

        # 계수 딕셔너리
        coefficients = {f: float(c) for f, c in zip(features, coeffs)}

        # 가장 영향력 있는 특성
        abs_coeffs = np.abs(coeffs)
        most_important_idx = np.argmax(abs_coeffs)
        most_important = features[most_important_idx]

        meta = {
            "features": features,
            "target": target,
            "n_train": int(len(train_df)),
            "n_test": int(len(test_df)),
            "coefficients": coefficients,
            "intercept": float(intercept),
            "r2_train": train_metrics["r2"],
            "r2_test": test_metrics["r2"],
            "mse_test": test_metrics["mse"],
            "rmse_test": test_metrics["rmse"],
            "mae_test": test_metrics["mae"],
            "r2_interpretation": _interpret_r2(test_metrics["r2"]),
            "most_important_feature": most_important,
            "most_important_coeff": float(coeffs[most_important_idx]),
        }

        result = {"type": "plotly", "title": title, "fig": fig.to_dict(), "meta": meta}
        return result, meta

    def description_builder(_df: pd.DataFrame, _result_obj: Dict[str, Any], meta: Dict[str, Any]) -> str:
        parts = []
        parts.append(f"선형 회귀 분석을 수행했습니다.")
        parts.append(f"학습 데이터: {meta['n_train']}개, 테스트 데이터: {meta['n_test']}개")

        r2 = meta.get("r2_test", 0)
        interp = meta.get("r2_interpretation", "")
        parts.append(f"테스트 R² = {r2:.4f} ({interp})")

        rmse = meta.get("rmse_test", 0)
        parts.append(f"RMSE = {rmse:.4f}")

        most_imp = meta.get("most_important_feature")
        if most_imp:
            coeff = meta.get("most_important_coeff", 0)
            direction = "양의" if coeff > 0 else "음의"
            parts.append(f"가장 영향력 있는 특성: '{most_imp}' ({direction} 관계)")

        return " ".join(parts)

    return safe_run_tool(
        raw_args=args,
        core_fn=core_fn,
        title="linear_regression",
        ext="json",
        description_builder=description_builder,
    )
