"""Session management endpoints."""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, HTTPException

from ..config import settings
from ..database import get_db
from ..models import SessionCreateRequest, SessionInfo
from ..services.adk_client import create_adk_session
from ..services.csv_store import csv_store
from ..services.plotly_store import plotly_store

router = APIRouter(prefix="/api/sessions", tags=["sessions"])
log = logging.getLogger(__name__)


@router.post("", response_model=SessionInfo)
async def create_session(req: SessionCreateRequest):
    """Create a new session – registers both on ADK and in the local DB."""
    log.info("Creating session: user_id=%s, session_id=%s", req.user_id, req.session_id)

    # 1. Create on ADK side
    try:
        result = await create_adk_session(req.user_id, req.session_id, req.state)
        log.info("ADK session created: %s", result)
    except Exception as exc:
        log.warning("ADK session creation failed: %s", exc, exc_info=True)
        raise HTTPException(502, detail=f"ADK session creation failed: {exc}")

    # 2. Persist locally
    db = await get_db()
    try:
        await db.execute(
            """INSERT OR REPLACE INTO sessions
               (session_id, user_id, session_name, created_at, expired)
               VALUES (?, ?, ?, datetime('now'), 0)""",
            (req.session_id, req.user_id, req.session_name),
        )
        await db.commit()

        cur = await db.execute(
            "SELECT * FROM sessions WHERE session_id = ?", (req.session_id,)
        )
        row = await cur.fetchone()
    finally:
        await db.close()

    return SessionInfo(
        session_id=row["session_id"],
        user_id=row["user_id"],
        session_name=row["session_name"],
        created_at=row["created_at"],
        expired=bool(row["expired"]),
    )


@router.get("", response_model=list[SessionInfo])
async def list_sessions(user_id: str | None = None):
    """List all active (non-expired) sessions, optionally filtered by user_id."""
    db = await get_db()
    try:
        if user_id:
            cur = await db.execute(
                "SELECT * FROM sessions WHERE user_id = ? AND expired = 0 ORDER BY created_at DESC",
                (user_id,),
            )
        else:
            cur = await db.execute(
                "SELECT * FROM sessions WHERE expired = 0 ORDER BY created_at DESC"
            )
        rows = await cur.fetchall()
    finally:
        await db.close()

    return [
        SessionInfo(
            session_id=r["session_id"],
            user_id=r["user_id"],
            session_name=r["session_name"],
            created_at=r["created_at"],
            expired=bool(r["expired"]),
        )
        for r in rows
    ]


@router.delete("/{session_id}")
async def delete_session(session_id: str):
    """Mark session as expired and clean up stored data."""
    db = await get_db()
    try:
        await db.execute(
            "UPDATE sessions SET expired = 1 WHERE session_id = ?", (session_id,)
        )
        await db.commit()
    finally:
        await db.close()

    csv_store.remove_by_session(session_id)
    plotly_store.remove_by_prefix(session_id)

    return {"ok": True, "session_id": session_id}


async def cleanup_expired_sessions() -> int:
    """Delete sessions older than SESSION_TTL_HOURS. Returns count deleted."""
    cutoff = datetime.now(timezone.utc) - timedelta(hours=settings.SESSION_TTL_HOURS)
    cutoff_str = cutoff.strftime("%Y-%m-%d %H:%M:%S")

    db = await get_db()
    try:
        cur = await db.execute(
            "SELECT session_id FROM sessions WHERE expired = 0 AND created_at < ?",
            (cutoff_str,),
        )
        rows = await cur.fetchall()

        for row in rows:
            sid = row["session_id"]
            csv_store.remove_by_session(sid)
            plotly_store.remove_by_prefix(sid)

        await db.execute(
            "UPDATE sessions SET expired = 1 WHERE expired = 0 AND created_at < ?",
            (cutoff_str,),
        )
        await db.commit()
    finally:
        await db.close()

    return len(rows)
