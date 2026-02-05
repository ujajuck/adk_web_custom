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
"""


async def init_db() -> None:
    async with aiosqlite.connect(settings.DB_PATH) as db:
        await db.executescript(_SCHEMA)
        await db.commit()


async def get_db() -> aiosqlite.Connection:
    db = await aiosqlite.connect(settings.DB_PATH)
    db.row_factory = aiosqlite.Row
    return db
