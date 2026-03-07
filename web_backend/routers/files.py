"""Workspace file listing and upload endpoints."""

from __future__ import annotations

import logging
import os
import shutil
import uuid
from pathlib import Path

from fastapi import APIRouter, File, Form, HTTPException, UploadFile

from ..config import settings

router = APIRouter(prefix="/api/files", tags=["files"])
log = logging.getLogger(__name__)

# Upload directory
UPLOAD_DIR = Path(settings.DATA_DIR) / "uploads"
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)


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


@router.post("/upload")
async def upload_file(
    file: UploadFile = File(...),
    session_id: str = Form(""),
):
    """Upload a file for the current session."""
    if not file.filename:
        raise HTTPException(400, detail="No filename provided")

    # Create session subdirectory
    session_dir = UPLOAD_DIR / (session_id or "default")
    session_dir.mkdir(parents=True, exist_ok=True)

    # Generate unique filename
    ext = Path(file.filename).suffix
    unique_name = f"{uuid.uuid4().hex[:8]}_{file.filename}"
    dest_path = session_dir / unique_name

    try:
        with open(dest_path, "wb") as f:
            shutil.copyfileobj(file.file, f)

        log.info("File uploaded: %s -> %s", file.filename, dest_path)
        return {
            "ok": True,
            "filename": file.filename,
            "path": str(dest_path),
            "size": dest_path.stat().st_size,
        }
    except Exception as e:
        log.error("Upload failed: %s", e)
        raise HTTPException(500, detail=str(e))
