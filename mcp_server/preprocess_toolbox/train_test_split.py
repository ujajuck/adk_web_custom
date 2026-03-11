from __future__ import annotations

from typing import Any, Dict, Optional, Tuple, List

import numpy as np
import pandas as pd

from ..utils.plot_io import make_job_id
from ..utils.path_resolver import save_resource


def train_test_split(args: Dict[str, Any]) -> Dict[str, Any]:
    """데이터를 학습/테스트(또는 학습/검증/테스트) 세트로 분리한다.

    데이터 입력 방식 (source_type으로 구분):
      1. artifact (권장):
         {
           "source_type": "artifact",
           "artifact_name": "data.csv",
           "test_size": 0.2
         }

      2. file:
         {
           "source_type": "file",
           "path": "C:/data/dataset.csv",
           "test_size": 0.2,
           "val_size": 0.1
         }

      3. direct:
         {
           "source_type": "direct",
           "data": [...],
           "test_size": 0.2
         }

    분리 파라미터:
      - test_size (float, default=0.2): 테스트 세트 비율 (0~1)
      - val_size (float, optional): 검증 세트 비율 (0~1). 지정 시 3분할
      - stratify (str, optional): 층화 추출할 범주형 컬럼명
      - shuffle (bool, default=True): 분리 전 섞기 여부
      - random_state (int, default=42): 랜덤 시드

    출력:
      {
        "status": "success",
        "outputs": [
          {"type": "resource_link", "uri": "mcp://resource/train.csv", ...},
          {"type": "resource_link", "uri": "mcp://resource/test.csv", ...},
          (optional) {"type": "resource_link", "uri": "mcp://resource/val.csv", ...}
        ]
      }
    """
    from ..schema.base_source import resolve_dataframe

    source = args.get("source") or args
    df = resolve_dataframe(source)

    if df is None or df.empty:
        raise ValueError("입력 데이터가 비어있습니다.")

    test_size = float(args.get("test_size", 0.2))
    val_size = args.get("val_size")
    stratify_col = args.get("stratify")
    shuffle = bool(args.get("shuffle", True))
    random_state = int(args.get("random_state", 42))

    n = len(df)
    np.random.seed(random_state)

    if shuffle:
        indices = np.random.permutation(n)
    else:
        indices = np.arange(n)

    # 층화 추출
    if stratify_col and stratify_col in df.columns:
        train_idx, test_idx, val_idx = _stratified_split(
            df, stratify_col, test_size, val_size, random_state
        )
    else:
        # 단순 분할
        n_test = int(n * test_size)
        n_val = int(n * float(val_size)) if val_size else 0

        test_idx = indices[:n_test]
        val_idx = indices[n_test:n_test + n_val] if n_val > 0 else []
        train_idx = indices[n_test + n_val:]

    train_df = df.iloc[train_idx].reset_index(drop=True)
    test_df = df.iloc[test_idx].reset_index(drop=True)

    job_id = make_job_id()
    outputs = []

    # 학습 세트 저장
    train_csv = train_df.to_csv(index=False)
    train_uri = save_resource(f"{job_id}_train.csv", train_csv.encode("utf-8"))
    outputs.append({
        "type": "resource_link",
        "uri": train_uri,
        "artifact_name": f"{job_id}_train.csv",
        "mime_type": "text/csv",
        "title": "Train Set",
        "n_rows": len(train_df),
    })

    # 테스트 세트 저장
    test_csv = test_df.to_csv(index=False)
    test_uri = save_resource(f"{job_id}_test.csv", test_csv.encode("utf-8"))
    outputs.append({
        "type": "resource_link",
        "uri": test_uri,
        "artifact_name": f"{job_id}_test.csv",
        "mime_type": "text/csv",
        "title": "Test Set",
        "n_rows": len(test_df),
    })

    # 검증 세트 (옵션)
    if val_size and len(val_idx) > 0:
        val_df = df.iloc[val_idx].reset_index(drop=True)
        val_csv = val_df.to_csv(index=False)
        val_uri = save_resource(f"{job_id}_val.csv", val_csv.encode("utf-8"))
        outputs.append({
            "type": "resource_link",
            "uri": val_uri,
            "artifact_name": f"{job_id}_val.csv",
            "mime_type": "text/csv",
            "title": "Validation Set",
            "n_rows": len(val_df),
        })
        description = f"데이터를 학습({len(train_df)}행)/검증({len(val_df)}행)/테스트({len(test_df)}행)로 분리했습니다."
    else:
        description = f"데이터를 학습({len(train_df)}행)/테스트({len(test_df)}행)로 분리했습니다."

    return {
        "status": "success",
        "outputs": outputs,
        "description": description,
    }


def _stratified_split(
    df: pd.DataFrame,
    stratify_col: str,
    test_size: float,
    val_size: Optional[float],
    random_state: int,
) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
    """층화 추출 기반 분할."""
    np.random.seed(random_state)

    train_indices = []
    test_indices = []
    val_indices = []

    for _, group in df.groupby(stratify_col):
        n = len(group)
        indices = group.index.to_numpy()
        np.random.shuffle(indices)

        n_test = int(n * test_size)
        n_val = int(n * float(val_size)) if val_size else 0

        test_indices.extend(indices[:n_test])
        val_indices.extend(indices[n_test:n_test + n_val])
        train_indices.extend(indices[n_test + n_val:])

    return (
        np.array(train_indices),
        np.array(test_indices),
        np.array(val_indices),
    )
