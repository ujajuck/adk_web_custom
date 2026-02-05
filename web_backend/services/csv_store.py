"""In-memory DataFrame cache backed by on-disk CSV copies."""

from __future__ import annotations

import shutil
from pathlib import Path
from typing import Any

import pandas as pd

from ..config import settings


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
        df = pd.read_csv(source)

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
        df.to_csv(dest_file, index=False)

        self._frames[file_id] = df
        self._filenames[file_id] = filename
        self._paths[file_id] = dest_file

    # ── read ───────────────────────────────────────────────

    def get_page(
        self,
        file_id: str,
        offset: int = 0,
        limit: int = 50,
    ) -> dict[str, Any]:
        """Return a page of rows as list[dict] plus metadata."""
        df = self._frames.get(file_id)
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
            raise KeyError(file_id)
        return {
            "file_id": file_id,
            "filename": self._filenames.get(file_id, ""),
            "total_rows": len(df),
            "total_cols": len(df.columns),
            "columns": list(df.columns),
        }

    def get_download_path(self, file_id: str) -> Path | None:
        return self._paths.get(file_id)

    def has(self, file_id: str) -> bool:
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
