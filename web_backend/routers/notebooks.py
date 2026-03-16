"""Notebooks API - save/load chat history per user."""

from __future__ import annotations

import json
import uuid
from datetime import datetime
from typing import Any, List, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from ..database import get_db

router = APIRouter(prefix="/api/notebooks", tags=["notebooks"])


class NotebookCreate(BaseModel):
    user_id: str
    session_id: str
    title: str
    messages: List[dict]
    metadata: Optional[dict] = None


class NotebookUpdate(BaseModel):
    title: Optional[str] = None
    messages: Optional[List[dict]] = None


class NotebookShare(BaseModel):
    is_shared: bool


class NotebookResponse(BaseModel):
    notebook_id: str
    user_id: str
    session_id: str
    title: str
    messages: List[dict]
    metadata: Optional[dict] = None
    is_shared: bool
    created_at: str
    updated_at: str


@router.post("", response_model=NotebookResponse)
async def create_notebook(req: NotebookCreate):
    """Create a new notebook (save chat history)."""
    notebook_id = f"nb_{uuid.uuid4().hex[:12]}"
    now = datetime.utcnow().isoformat()
    messages_json = json.dumps(req.messages, ensure_ascii=False)
    metadata_json = json.dumps(req.metadata or {}, ensure_ascii=False)

    db = await get_db()
    try:
        await db.execute(
            """
            INSERT INTO notebooks (notebook_id, user_id, session_id, title, messages, metadata, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (notebook_id, req.user_id, req.session_id, req.title, messages_json, metadata_json, now, now),
        )
        await db.commit()
    finally:
        await db.close()

    return NotebookResponse(
        notebook_id=notebook_id,
        user_id=req.user_id,
        session_id=req.session_id,
        title=req.title,
        messages=req.messages,
        metadata=req.metadata,
        is_shared=False,
        created_at=now,
        updated_at=now,
    )


@router.get("/user/{user_id}", response_model=List[NotebookResponse])
async def get_user_notebooks(user_id: str):
    """Get all notebooks for a user."""
    db = await get_db()
    try:
        cursor = await db.execute(
            """
            SELECT notebook_id, user_id, session_id, title, messages, metadata, is_shared, created_at, updated_at
            FROM notebooks
            WHERE user_id = ?
            ORDER BY updated_at DESC
            """,
            (user_id,),
        )
        rows = await cursor.fetchall()
    finally:
        await db.close()

    return [
        NotebookResponse(
            notebook_id=row["notebook_id"],
            user_id=row["user_id"],
            session_id=row["session_id"],
            title=row["title"],
            messages=json.loads(row["messages"]),
            metadata=json.loads(row["metadata"] or "{}"),
            is_shared=bool(row["is_shared"]),
            created_at=row["created_at"],
            updated_at=row["updated_at"],
        )
        for row in rows
    ]


@router.get("/shared", response_model=List[NotebookResponse])
async def get_shared_notebooks():
    """Get all shared notebooks."""
    db = await get_db()
    try:
        cursor = await db.execute(
            """
            SELECT notebook_id, user_id, session_id, title, messages, metadata, is_shared, created_at, updated_at
            FROM notebooks
            WHERE is_shared = 1
            ORDER BY updated_at DESC
            """,
        )
        rows = await cursor.fetchall()
    finally:
        await db.close()

    return [
        NotebookResponse(
            notebook_id=row["notebook_id"],
            user_id=row["user_id"],
            session_id=row["session_id"],
            title=row["title"],
            messages=json.loads(row["messages"]),
            metadata=json.loads(row["metadata"] or "{}"),
            is_shared=bool(row["is_shared"]),
            created_at=row["created_at"],
            updated_at=row["updated_at"],
        )
        for row in rows
    ]


@router.get("/{notebook_id}", response_model=NotebookResponse)
async def get_notebook(notebook_id: str):
    """Get a specific notebook."""
    db = await get_db()
    try:
        cursor = await db.execute(
            """
            SELECT notebook_id, user_id, session_id, title, messages, metadata, is_shared, created_at, updated_at
            FROM notebooks
            WHERE notebook_id = ?
            """,
            (notebook_id,),
        )
        row = await cursor.fetchone()
    finally:
        await db.close()

    if not row:
        raise HTTPException(404, detail=f"Notebook not found: {notebook_id}")

    return NotebookResponse(
        notebook_id=row["notebook_id"],
        user_id=row["user_id"],
        session_id=row["session_id"],
        title=row["title"],
        messages=json.loads(row["messages"]),
        is_shared=bool(row["is_shared"]),
        created_at=row["created_at"],
        updated_at=row["updated_at"],
    )


@router.patch("/{notebook_id}/share", response_model=NotebookResponse)
async def toggle_share(notebook_id: str, req: NotebookShare):
    """Toggle notebook sharing."""
    now = datetime.utcnow().isoformat()
    db = await get_db()
    try:
        await db.execute(
            """
            UPDATE notebooks SET is_shared = ?, updated_at = ? WHERE notebook_id = ?
            """,
            (1 if req.is_shared else 0, now, notebook_id),
        )
        await db.commit()

        cursor = await db.execute(
            """
            SELECT notebook_id, user_id, session_id, title, messages, metadata, is_shared, created_at, updated_at
            FROM notebooks WHERE notebook_id = ?
            """,
            (notebook_id,),
        )
        row = await cursor.fetchone()
    finally:
        await db.close()

    if not row:
        raise HTTPException(404, detail=f"Notebook not found: {notebook_id}")

    return NotebookResponse(
        notebook_id=row["notebook_id"],
        user_id=row["user_id"],
        session_id=row["session_id"],
        title=row["title"],
        messages=json.loads(row["messages"]),
        is_shared=bool(row["is_shared"]),
        created_at=row["created_at"],
        updated_at=row["updated_at"],
    )


@router.delete("/{notebook_id}")
async def delete_notebook(notebook_id: str):
    """Delete a notebook."""
    db = await get_db()
    try:
        cursor = await db.execute(
            "SELECT notebook_id FROM notebooks WHERE notebook_id = ?",
            (notebook_id,),
        )
        row = await cursor.fetchone()
        if not row:
            raise HTTPException(404, detail=f"Notebook not found: {notebook_id}")

        await db.execute("DELETE FROM notebooks WHERE notebook_id = ?", (notebook_id,))
        await db.commit()
    finally:
        await db.close()

    return {"status": "deleted", "notebook_id": notebook_id}
