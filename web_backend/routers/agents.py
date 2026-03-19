"""Agents endpoint – returns available agents in the ADK app."""

from __future__ import annotations

from fastapi import APIRouter

from ..services.adk_client import list_agents

router = APIRouter(prefix="/api/agents", tags=["agents"])


@router.get("")
async def get_agents():
    """Return list of agent names available in the ADK app."""
    agents = await list_agents()
    return {"agents": agents}
