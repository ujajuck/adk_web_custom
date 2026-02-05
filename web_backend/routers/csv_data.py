"""CSV data endpoints – paginated rows and file download."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import FileResponse

from ..models import CsvPageResponse
from ..services.csv_store import csv_store

router = APIRouter(prefix="/api/csv", tags=["csv"])


@router.get("/{file_id}", response_model=CsvPageResponse)
async def get_csv_page(
    file_id: str,
    offset: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=5000),
):
    """Return a paginated slice of the CSV file as JSON rows."""
    try:
        page = csv_store.get_page(file_id, offset=offset, limit=limit)
    except KeyError:
        raise HTTPException(404, detail=f"CSV file not found: {file_id}")
    return page


@router.get("/{file_id}/download")
async def download_csv(file_id: str):
    """Download the original CSV file."""
    path = csv_store.get_download_path(file_id)
    if path is None or not path.exists():
        raise HTTPException(404, detail=f"CSV file not found: {file_id}")

    return FileResponse(
        path=str(path),
        media_type="text/csv; charset=utf-8",
        filename=path.name,
    )


@router.get("/{file_id}/meta")
async def get_csv_meta(file_id: str):
    """Return metadata (columns, row count) for a CSV file."""
    try:
        meta = csv_store.get_meta(file_id)
    except KeyError:
        raise HTTPException(404, detail=f"CSV file not found: {file_id}")
    return meta
