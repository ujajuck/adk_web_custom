from pathlib import Path
import pandas as pd
import os
from dotenv import load_dotenv
load_dotenv("mcp_server/.env")

ADK_ARTIFACT_ROOT = os.environ.get("ADK_ARTIFACT_ROOT")

def resolve_artifact_path(artifact_locator: dict) -> str:
    """
    artifact_locator(dict) -> 실제 CSV 파일 경로(str)
    """
    try:
        session_id = artifact_locator["session_id"]
        artifact_name = artifact_locator["artifact_name"]
        version = str(artifact_locator["version"])
        file_name = artifact_locator.get("file_name", artifact_name)
    except KeyError as e:
        raise ValueError(f"artifact_locator 필드 누락: {e}")

    path = (
        Path(ADK_ARTIFACT_ROOT)
        / "user"
        / "sessions"
        / session_id
        / "artifacts"
        / artifact_name
        / "versions"
        / version
        / file_name
    )

    # 🔒 path traversal 방어
    path = path.resolve()
    root = Path(ADK_ARTIFACT_ROOT).resolve()
    if root not in path.parents:
        raise ValueError("잘못된 artifact 경로입니다.")

    return str(path)
