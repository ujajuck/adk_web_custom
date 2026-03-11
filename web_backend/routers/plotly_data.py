"""Plotly figure retrieval endpoint."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException

from ..services.plotly_store import plotly_store

router = APIRouter(prefix="/api/plotly", tags=["plotly"])


@router.get("/{fig_id}")
async def get_plotly_fig(fig_id: str):
    """Return a stored Plotly figure JSON by its fig_id."""
    fig = plotly_store.get(fig_id)
    if fig is None:
        raise HTTPException(404, detail=f"Plotly figure not found: {fig_id}")
    return fig
