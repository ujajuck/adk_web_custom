import os
from pathlib import Path

_BASE = Path(__file__).resolve().parent


class Settings:
    ADK_BASE_URL: str = os.getenv("ADK_BASE_URL", "http://127.0.0.1:8000")
    ADK_APP_NAME: str = os.getenv("ADK_APP_NAME", "adk_backend")
    ADK_ARTIFACT_ROOT: str = os.getenv(
        "ADK_ARTIFACT_ROOT", str(_BASE / ".adk" / "artifacts")
    )
    WORKSPACE_FILES_DIR: str = os.getenv("WORKSPACE_FILES_DIR", str(_BASE / "data"))
    DATA_DIR: str = os.getenv("WEB_BACKEND_DATA_DIR", str(_BASE / "csv_store"))
    DB_PATH: str = os.getenv("WEB_BACKEND_DB_PATH", str(_BASE / "web_backend.db"))
    HOST: str = os.getenv("WEB_BACKEND_HOST", "0.0.0.0")
    PORT: int = int(os.getenv("WEB_BACKEND_PORT", "8080"))
    SESSION_TTL_HOURS: int = int(os.getenv("SESSION_TTL_HOURS", "24"))


settings = Settings()
Path(settings.DATA_DIR).mkdir(parents=True, exist_ok=True)
