"""Workspace file listing endpoint – replaces the Next.js API route."""

from __future__ import annotations

import logging
import os
from pathlib import Path

from fastapi import APIRouter, HTTPException

from ..config import settings

router = APIRouter(prefix="/api/files", tags=["files"])
log = logging.getLogger(__name__)


@router.get("")
async def list_workspace_files():
    """List files in the configured WORKSPACE_FILES_DIR."""
    root = settings.WORKSPACE_FILES_DIR
    log.info("WORKSPACE_FILES_DIR = %s", root)

    if not root:
        raise HTTPException(500, detail="WORKSPACE_FILES_DIR is not configured")

    root_path = Path(root)
    log.info("Path exists: %s, is_dir: %s", root_path.exists(), root_path.is_dir() if root_path.exists() else "N/A")

    if not root_path.exists():
        return {"ok": True, "root_dir": root, "files": [], "error": f"Path does not exist: {root}"}

    try:
        entries = sorted(root_path.iterdir())
        files = [
            {"name": e.name, "size": e.stat().st_size}
            for e in entries
            if e.is_file()
        ]
        return {"ok": True, "root_dir": root, "files": files}
    except OSError as exc:
        raise HTTPException(500, detail=str(exc))
