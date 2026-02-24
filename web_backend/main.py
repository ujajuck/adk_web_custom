"""FastAPI web backend – bridges the Next.js frontend with the ADK agent."""

from __future__ import annotations

import asyncio
import logging

from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from .config import settings
from .database import init_db
from .routers import chat, csv_data, files, plotly_data, sessions

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)-8s %(name)s  %(message)s",
)
log = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # ── startup ──
    log.info("Initializing SQLite database …")
    await init_db()
    log.info("Database ready  (%s)", settings.DB_PATH)

    # background: periodic session cleanup
    async def _cleanup_loop():
        from .routers.sessions import cleanup_expired_sessions

        while True:
            await asyncio.sleep(3600)  # every hour
            try:
                n = await cleanup_expired_sessions()
                if n:
                    log.info("Cleaned up %d expired sessions", n)
            except Exception:
                log.exception("Session cleanup error")

    task = asyncio.create_task(_cleanup_loop())

    yield

    # ── shutdown ──
    task.cancel()
    log.info("Web backend shutting down.")


app = FastAPI(
    title="ADK Web Backend",
    version="0.1.0",
    lifespan=lifespan,
)

# CORS – allow the Next.js dev server (and any origin for development)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Validation error handler – log 422 errors with details
@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    body = await request.body()
    log.warning(
        "Validation error on %s %s\n  body: %s\n  errors: %s",
        request.method,
        request.url.path,
        body.decode("utf-8", errors="replace")[:500],
        exc.errors(),
    )
    return JSONResponse(
        status_code=422,
        content={"detail": exc.errors()},
    )


# Register routers
app.include_router(sessions.router)
app.include_router(chat.router)
app.include_router(csv_data.router)
app.include_router(plotly_data.router)
app.include_router(files.router)


@app.get("/health")
async def health():
    return {"status": "ok"}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "web_backend.main:app",
        host=settings.HOST,
        port=settings.PORT,
        reload=True,
    )
