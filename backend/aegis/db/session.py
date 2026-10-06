"""Async engine + session factory. SQLite runs in WAL mode so the API can read
while workers write."""
from __future__ import annotations

import os
from contextlib import asynccontextmanager
from datetime import datetime, timezone

from sqlalchemy import event
from sqlalchemy.ext.asyncio import (AsyncEngine, AsyncSession, async_sessionmaker,
                                    create_async_engine)

from .models import Base

_engine: AsyncEngine | None = None
_sessionmaker: async_sessionmaker[AsyncSession] | None = None


def _sqlite_path(url: str) -> str | None:
    prefix = "sqlite+aiosqlite:///"
    return url[len(prefix):] if url.startswith(prefix) else None


async def init_db(database_url: str) -> None:
    global _engine, _sessionmaker
    path = _sqlite_path(database_url)
    if path and path != ":memory:":
        os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    _engine = create_async_engine(database_url)

    @event.listens_for(_engine.sync_engine, "connect")
    def _pragmas(dbapi_conn, _):  # noqa: ANN001
        cur = dbapi_conn.cursor()
        cur.execute("PRAGMA journal_mode=WAL")
        cur.execute("PRAGMA foreign_keys=ON")
        cur.execute("PRAGMA busy_timeout=15000")
        cur.close()

    async with _engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        await conn.run_sync(_add_missing_columns)
    _sessionmaker = async_sessionmaker(_engine, expire_on_commit=False)


def _add_missing_columns(sync_conn) -> None:
    """Minimal forward migration: add columns introduced after a table was
    created (create_all never alters existing tables). Additive only."""
    from sqlalchemy import inspect, text
    insp = inspect(sync_conn)
    for table in Base.metadata.sorted_tables:
        existing = {c["name"] for c in insp.get_columns(table.name)}
        for col in table.columns:
            if col.name not in existing:
                ddl = col.type.compile(dialect=sync_conn.dialect)
                sync_conn.execute(text(f'ALTER TABLE {table.name} ADD COLUMN "{col.name}" {ddl}'))
    # rows created before visibility existed: samples and red team are public
    if "visibility" in {c["name"] for c in insp.get_columns("analyses")}:
        sync_conn.execute(text("UPDATE analyses SET visibility = CASE WHEN source IN "
                               "('sample','redteam') THEN 'public' ELSE 'private' END "
                               "WHERE visibility IS NULL"))


async def close_db() -> None:
    global _engine
    if _engine is not None:
        await _engine.dispose()
        _engine = None


@asynccontextmanager
async def session_scope():
    """A session that commits on success and rolls back on error."""
    if _sessionmaker is None:
        raise RuntimeError("database not initialised")
    async with _sessionmaker() as s:
        try:
            yield s
            await s.commit()
        except Exception:
            await s.rollback()
            raise


def as_utc(dt: datetime | None) -> datetime | None:
    """SQLite drops tzinfo; every stored datetime is UTC."""
    if dt is None:
        return None
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


def iso(dt: datetime | None) -> str | None:
    dt = as_utc(dt)
    return dt.isoformat().replace("+00:00", "Z") if dt else None
