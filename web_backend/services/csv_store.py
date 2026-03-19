"""In-memory DataFrame cache backed by on-disk CSV copies."""

from __future__ import annotations

import logging
import shutil
from pathlib import Path
from typing import Any

import pandas as pd

from ..config import settings

log = logging.getLogger(__name__)

# 한국어 CSV 파일에서 자주 사용되는 인코딩 목록 (우선순위 순)
_ENCODINGS = ["utf-8", "cp949", "euc-kr", "utf-8-sig", "latin1"]


def _read_csv_with_encoding(path: Path) -> pd.DataFrame:
    """여러 인코딩을 시도하여 CSV 파일을 읽습니다."""
    last_error: Exception | None = None
    for enc in _ENCODINGS:
        try:
            df = pd.read_csv(path, encoding=enc)
            log.debug("CSV loaded with encoding: %s", enc)
            return df
        except (UnicodeDecodeError, UnicodeError) as e:
            last_error = e
            continue
    # 모든 인코딩 실패 시 마지막 에러 raise
    raise last_error or ValueError(f"Cannot decode CSV: {path}")


class CsvStore:
    """Stores DataFrames in memory keyed by file_id, with CSV files on disk."""

    def __init__(self) -> None:
        self._frames: dict[str, pd.DataFrame] = {}
        self._filenames: dict[str, str] = {}
        self._paths: dict[str, Path] = {}

    # ── write ──────────────────────────────────────────────

    def store_from_path(
        self,
        file_id: str,
        source_path: str | Path,
        filename: str,
    ) -> pd.DataFrame:
        """Read a CSV from *source_path*, cache the DataFrame, and copy the
        file into the local data directory for later download."""
        source = Path(source_path)
        df = _read_csv_with_encoding(source)

        dest = Path(settings.DATA_DIR) / file_id
        dest.mkdir(parents=True, exist_ok=True)
        dest_file = dest / filename
        shutil.copy2(source, dest_file)

        self._frames[file_id] = df
        self._filenames[file_id] = filename
        self._paths[file_id] = dest_file
        return df

    def store_from_dataframe(
        self,
        file_id: str,
        df: pd.DataFrame,
        filename: str,
    ) -> None:
        """Store an already-loaded DataFrame."""
        dest = Path(settings.DATA_DIR) / file_id
        dest.mkdir(parents=True, exist_ok=True)
        dest_file = dest / filename
        df.to_csv(dest_file, index=False, encoding="utf-8-sig")

        self._frames[file_id] = df
        self._filenames[file_id] = filename
        self._paths[file_id] = dest_file

    # ── read ───────────────────────────────────────────────

    def _try_restore(self, file_id: str) -> "pd.DataFrame | None":
        """서버 재시작 후 디스크에 파일이 있으면 메모리로 복원한다."""
        data_dir = Path(settings.DATA_DIR) / file_id
        if not data_dir.exists():
            return None
        csv_files = sorted(data_dir.glob("*.csv"))
        if not csv_files:
            return None
        csv_file = csv_files[0]
        try:
            df = _read_csv_with_encoding(csv_file)
            self._frames[file_id] = df
            self._filenames[file_id] = csv_file.name
            self._paths[file_id] = csv_file
            log.info("CSV restored from disk: %s / %s", file_id, csv_file.name)
            return df
        except Exception as exc:
            log.warning("Failed to restore CSV %s: %s", file_id, exc)
            return None

    def get_page(
        self,
        file_id: str,
        offset: int = 0,
        limit: int = 50,
    ) -> dict[str, Any]:
        """Return a page of rows as list[dict] plus metadata."""
        df = self._frames.get(file_id)
        if df is None:
            df = self._try_restore(file_id)
        if df is None:
            raise KeyError(file_id)

        total = len(df)
        page = df.iloc[offset : offset + limit]
        rows = page.where(page.notna(), None).to_dict(orient="records")

        return {
            "file_id": file_id,
            "filename": self._filenames.get(file_id, ""),
            "columns": list(df.columns),
            "rows": rows,
            "total_rows": total,
            "offset": offset,
            "limit": limit,
        }

    def get_meta(self, file_id: str) -> dict[str, Any]:
        df = self._frames.get(file_id)
        if df is None:
            df = self._try_restore(file_id)
        if df is None:
            raise KeyError(file_id)
        return {
            "file_id": file_id,
            "filename": self._filenames.get(file_id, ""),
            "total_rows": len(df),
            "total_cols": len(df.columns),
            "columns": list(df.columns),
        }

    def get_download_path(self, file_id: str) -> Path | None:
        if file_id not in self._paths:
            self._try_restore(file_id)
        return self._paths.get(file_id)

    def has(self, file_id: str) -> bool:
        if file_id not in self._frames:
            self._try_restore(file_id)
        return file_id in self._frames

    # ── cleanup ────────────────────────────────────────────

    def remove(self, file_id: str) -> None:
        self._frames.pop(file_id, None)
        self._filenames.pop(file_id, None)
        p = self._paths.pop(file_id, None)
        if p and p.parent.exists():
            shutil.rmtree(p.parent, ignore_errors=True)

    def remove_by_session(self, session_id: str) -> None:
        to_del = [fid for fid in self._frames if fid.startswith(session_id)]
        for fid in to_del:
            self.remove(fid)


# singleton
csv_store = CsvStore()
