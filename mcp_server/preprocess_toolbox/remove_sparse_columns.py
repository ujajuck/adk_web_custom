import pandas as pd
from typing import Any,Dict
from ..utils.path_resolver import resolve_artifact_path,get_mcp_resource_path 

async def remove_sparse_columns(
        artifact_locator:Dict[str,Any],
        threshold: float = 0.5
)-> Dict[str,Any]:
    """
    artifact_name을 포함하는 artifact_locator 로 읽어야 하는 파일의 정보만 받는다.
    threshold 이상의 결측을 가지는 컬럼 제거 후 리턴한다. 
    """
    if artifact_locator is None:
        return ValueError("데이터 입력이 필요합니다.")
    
    if not (0 < threshold < 1):
        raise ValueError("threshold 는 0과 1사이 실수여야 합니다.")
    
    csv_path = resolve_artifact_path(artifact_locator)
    file_name = artifact_locator["artifact_name"]
    df = pd.read_csv(csv_path)

    na_ratio = df.isna().mean(axis=0)
    remove_cols= na_ratio[na_ratio>=threshold].index.tolist()
    cleaned_df = df.drop(columns=remove_cols,errors="ignore")

    job_id = get_mcp_resource_path(cleaned_df,csv_path)

    return{
        "status" : "success",
        "outputs": [
            {
                "type": "resource_link",
                "uri":f"mcp://resource/{job_id}.csv",
                "filename":file_name,
                "mime_type" : "text/csv",
                "description":f"{threshold}이상의 결측 비율을 가진 컬럼을 제거한 데이터셋입니다."
            }
        ]
    }