"""Storage schema. One SQLite file holds analyses, their stage runs, the
campaign-graph entities, red-team runs and the audit trail.

The `analyses` table doubles as the job queue: `status` moves
queued -> running -> done | failed, with `attempts` and `next_attempt_at`
for retries. `external_id` (the AgentBoxD message id) is unique, which makes
webhook redelivery idempotent at the database level.
"""
from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import (JSON, DateTime, Float, ForeignKey, Index, Integer, String, Text,
                        UniqueConstraint)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Base(DeclarativeBase):
    pass


class Analysis(Base):
    __tablename__ = "analyses"

    id: Mapped[str] = mapped_column(String(32), primary_key=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, index=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow,
                                                 onupdate=utcnow)
    source: Mapped[str] = mapped_column(String(16), index=True)  # web|webhook|poller|redteam|sample
    status: Mapped[str] = mapped_column(String(16), default="queued", index=True)
    attempts: Mapped[int] = mapped_column(Integer, default=0)
    next_attempt_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    error: Mapped[str | None] = mapped_column(Text)

    # input
    raw: Mapped[str] = mapped_column(Text, default="")          # pasted text / .eml source
    raw_html: Mapped[str] = mapped_column(Text, default="")     # html part when delivered separately
    provider_scores: Mapped[dict] = mapped_column(JSON, default=dict)  # AgentBoxD phishing/injection
    external_id: Mapped[str | None] = mapped_column(String(255), unique=True)
    inbox_id: Mapped[str | None] = mapped_column(String(128))
    needs_fetch: Mapped[int] = mapped_column(Integer, default=0)  # envelope-only webhook

    # outcome (top-level copies for listing/filtering)
    subject: Mapped[str] = mapped_column(String(300), default="")
    sender: Mapped[str] = mapped_column(String(300), default="")
    label: Mapped[str | None] = mapped_column(String(16), index=True)
    score: Mapped[float | None] = mapped_column(Float)
    confidence: Mapped[float | None] = mapped_column(Float)
    duration_s: Mapped[float | None] = mapped_column(Float)
    result: Mapped[dict] = mapped_column(JSON, default=dict)
    share_token: Mapped[str] = mapped_column(String(64), unique=True)
    replied_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    # privacy: public (samples, red team) or private (unlisted; owner sees it in their feed)
    visibility: Mapped[str] = mapped_column(String(8), default="private", index=True)
    owner_hash: Mapped[str | None] = mapped_column(String(64), index=True)
    mailbox_id: Mapped[str | None] = mapped_column(String(32), index=True)
    labeled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    purged_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    __table_args__ = (Index("ix_queue", "status", "next_attempt_at", "created_at"),)


class Mailbox(Base):
    """A mailbox linked with Sign in with Google or Microsoft. Only the refresh
    token is stored, encrypted. `last_uid` holds the provider cursor (Gmail
    history id, or the newest Outlook received time in epoch seconds)."""
    __tablename__ = "mailboxes"

    id: Mapped[str] = mapped_column(String(32), primary_key=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    owner_hash: Mapped[str] = mapped_column(String(64), index=True)
    provider: Mapped[str] = mapped_column(String(16))
    email: Mapped[str] = mapped_column(String(320))
    host: Mapped[str] = mapped_column(String(255))
    port: Mapped[int] = mapped_column(Integer, default=993)
    secret: Mapped[str] = mapped_column(Text)            # AES-GCM ciphertext of the refresh token
    status: Mapped[str] = mapped_column(String(8), default="active")  # active|paused|error
    label_mode: Mapped[str] = mapped_column(String(16), default="gmail-api")
    uidvalidity: Mapped[int | None] = mapped_column(Integer)
    last_uid: Mapped[int] = mapped_column(Integer, default=0)
    last_checked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_error: Mapped[str | None] = mapped_column(String(300))
    retention_days: Mapped[int] = mapped_column(Integer, default=7)


class StageRun(Base):
    __tablename__ = "stage_runs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    analysis_id: Mapped[str] = mapped_column(ForeignKey("analyses.id", ondelete="CASCADE"),
                                             index=True)
    name: Mapped[str] = mapped_column(String(32))
    seq: Mapped[int] = mapped_column(Integer, default=0)
    status: Mapped[str] = mapped_column(String(16), default="pending")
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    duration_s: Mapped[float | None] = mapped_column(Float)
    summary: Mapped[str] = mapped_column(String(500), default="")
    error: Mapped[str | None] = mapped_column(String(500))

    __table_args__ = (UniqueConstraint("analysis_id", "name"),)


class Entity(Base):
    """One infrastructure indicator seen in one analysis (campaign graph edge)."""
    __tablename__ = "entities"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    analysis_id: Mapped[str] = mapped_column(ForeignKey("analyses.id", ondelete="CASCADE"),
                                             index=True)
    kind: Mapped[str] = mapped_column(String(16))   # sender|domain|url|phone|template
    value: Mapped[str] = mapped_column(String(500), index=True)

    __table_args__ = (UniqueConstraint("analysis_id", "kind", "value"),)


class RedteamRun(Base):
    __tablename__ = "redteam_runs"

    id: Mapped[str] = mapped_column(String(32), primary_key=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    seed: Mapped[int] = mapped_column(Integer)
    base_subject: Mapped[str] = mapped_column(String(300), default="")
    base_raw: Mapped[str] = mapped_column(Text)
    variants: Mapped[list] = mapped_column(JSON, default=list)  # [{index, axes, text, analysis_id}]


class ViewerCode(Base):
    """A browser's personal test-inbox code: mail that carries it is shown to that browser only."""
    __tablename__ = "viewer_codes"

    code: Mapped[str] = mapped_column(String(16), primary_key=True)
    owner_hash: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class SenderLink(Base):
    """Which browser a sender's test-inbox mail goes to, learned from their last coded email.
    Only a hash of the address is stored."""
    __tablename__ = "sender_links"

    sender_hash: Mapped[str] = mapped_column(String(64), primary_key=True)
    owner_hash: Mapped[str] = mapped_column(String(64), index=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class AuditEvent(Base):
    __tablename__ = "audit_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    ts: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, index=True)
    event: Mapped[str] = mapped_column(String(64))
    detail: Mapped[dict] = mapped_column(JSON, default=dict)
