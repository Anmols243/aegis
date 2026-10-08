"""FastAPI application factory.

Run:  uvicorn aegis.main:app --port 8000   (from backend/)
"""
from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from . import __version__
from .api.routes import private, public
from .core.config import get_settings
from .core.logging import get_logger, setup_logging
from .core.security import BodyLimitMiddleware, SecurityHeadersMiddleware, reset_limits
from .db.session import close_db, init_db
from .providers.agentboxd import AgentBoxD
from .providers.llm import LLMClient
from .workers.mailbox import MailboxPoller
from .workers.poller import poll_forever
from .workers.queue import Worker

log = get_logger("main")


@asynccontextmanager
async def lifespan(app: FastAPI):
    s = get_settings()
    await init_db(s.database_url)
    reset_limits()
    llm, agentboxd = LLMClient(s), AgentBoxD(s)
    worker = Worker(s, llm, agentboxd)
    app.state.worker = worker
    await worker.start()
    mailbox_poller = MailboxPoller(s, worker.notify)
    app.state.mailbox_poller = mailbox_poller
    await mailbox_poller.start()
    poller = None
    if s.agentboxd_polling:
        poller = asyncio.create_task(poll_forever(agentboxd, worker.notify))
    log.info("aegis started", extra={"version": __version__, "llm": s.llm_configured,
                                     "agentboxd": agentboxd.configured,
                                     "auth": bool(s.aegis_api_key)})
    if not s.aegis_api_key:
        log.warning("AEGIS_API_KEY not set: API is unauthenticated, bind to 127.0.0.1 only")
    try:
        yield
    finally:
        if poller:
            poller.cancel()
        await mailbox_poller.stop()
        await worker.stop()
        await llm.close()
        await close_db()


def create_app() -> FastAPI:
    setup_logging()
    s = get_settings()
    app = FastAPI(title="AEGIS", version=__version__, lifespan=lifespan,
                  docs_url="/api/docs", openapi_url="/api/openapi.json", redoc_url=None)
    app.include_router(public)
    app.include_router(private)
    app.add_middleware(SecurityHeadersMiddleware)
    if s.cors_origins:
        app.add_middleware(CORSMiddleware, allow_origins=s.cors_origins,
                           allow_methods=["GET", "POST"],
                           allow_headers=["Authorization", "Content-Type"])
    app.add_middleware(BodyLimitMiddleware,
                       default_limit=s.max_upload_bytes + 64 * 1024,  # multipart overhead
                       limits={"/api/v1/ingest/": s.max_webhook_bytes})
    return app


app = create_app()
