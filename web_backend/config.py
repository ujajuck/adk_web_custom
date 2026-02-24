import os
from pathlib import Path

_BASE = Path(__file__).resolve().parent
_ENV_PATH = _BASE / ".env"

# .env 파일에서 설정 로드 (기존 환경변수 덮어쓰기)
from dotenv import load_dotenv

if _ENV_PATH.exists():
    load_dotenv(_ENV_PATH, override=True)
    print(f"[config] Loaded .env from {_ENV_PATH}")
else:
    print(f"[config] .env not found at {_ENV_PATH}")


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

# 디버그 출력
print(f"[config] WORKSPACE_FILES_DIR = {settings.WORKSPACE_FILES_DIR}")
print(f"[config] ADK_BASE_URL = {settings.ADK_BASE_URL}")

Path(settings.DATA_DIR).mkdir(parents=True, exist_ok=True)
