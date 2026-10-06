"""Shared types for pipeline stages."""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any

from ..core.config import Settings
from ..providers.llm import LLMClient


@dataclass
class EmailArtifact:
    raw: str = ""
    headers: str = ""
    subject: str = ""
    sender: str = ""
    reply_to: str = ""
    to: str = ""
    date: str = ""
    message_id: str = ""
    text: str = ""
    html: str = ""
    attachments: list[str] = field(default_factory=list)

    def public(self) -> dict:
        d = asdict(self)
        return {"subject": d["subject"], "from": d["sender"], "reply_to": d["reply_to"],
                "to": d["to"], "date": d["date"], "text": d["text"],
                "html_available": bool(self.html), "attachments": d["attachments"]}

    def sources(self) -> tuple[str, ...]:
        """Everything a quoted excerpt may legitimately come from."""
        return (self.text, self.headers, self.subject, self.html, self.raw)


class Skip(Exception):
    """Raised by a stage that does not apply to this email."""


@dataclass
class StageResult:
    value: Any
    summary: str = ""


@dataclass
class PipelineContext:
    analysis_id: str
    source: str
    raw: str
    settings: Settings
    llm: LLMClient
    raw_html: str = ""
    provider_scores: dict = field(default_factory=dict)
    email: EmailArtifact | None = None
    results: dict[str, Any] = field(default_factory=dict)
