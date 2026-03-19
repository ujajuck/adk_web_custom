import aiosqlite

from .config import settings

_SCHEMA = """
CREATE TABLE IF NOT EXISTS sessions (
    session_id TEXT PRIMARY KEY,
    user_id    TEXT NOT NULL,
    session_name TEXT DEFAULT '',
    created_at TEXT DEFAULT (datetime('now')),
    expired    INTEGER DEFAULT 0
);

CREATE TABLE IF NOT EXISTS chat_jobs (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id         TEXT NOT NULL,
    session_id      TEXT NOT NULL,
    job_id          TEXT UNIQUE NOT NULL,
    request_message TEXT DEFAULT '',
    response_text   TEXT DEFAULT '',
    csv_meta        TEXT DEFAULT '[]',
    plotly_meta     TEXT DEFAULT '[]',
    created_at      TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS notebooks (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    notebook_id TEXT UNIQUE NOT NULL,
    user_id     TEXT NOT NULL,
    session_id  TEXT NOT NULL,
    title       TEXT NOT NULL,
    messages    TEXT DEFAULT '[]',
    metadata    TEXT DEFAULT '{}',
    is_shared   INTEGER DEFAULT 0,
    created_at  TEXT DEFAULT (datetime('now')),
    updated_at  TEXT DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_notebooks_user ON notebooks(user_id);
CREATE INDEX IF NOT EXISTS idx_notebooks_shared ON notebooks(is_shared);
"""


async def init_db() -> None:
    async with aiosqlite.connect(settings.DB_PATH) as db:
        await db.executescript(_SCHEMA)
        # 기존 DB에 metadata 컬럼 추가 (없는 경우만)
        try:
            await db.execute(
                "ALTER TABLE notebooks ADD COLUMN metadata TEXT DEFAULT '{}'"
            )
            await db.commit()
        except Exception:
            pass  # 이미 컬럼이 존재하면 무시


async def get_db() -> aiosqlite.Connection:
    db = await aiosqlite.connect(settings.DB_PATH)
    db.row_factory = aiosqlite.Row
    return db
