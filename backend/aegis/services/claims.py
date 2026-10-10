"""Personal test-inbox codes. Everyone mails the same address, so each browser gets a short
code (`AEGIS-7F3K2Q`) to put in the subject; mail that carries it belongs to that browser
and is listed for it alone. The first coded email also links its sender address to that
browser, so later mail from the same address needs no code (people forget it, and mail
written by hand never has it). Mail with neither is replied to by email, shown to nobody."""
from __future__ import annotations

import hashlib
import re
import secrets
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from ..db.models import SenderLink, ViewerCode

_ALPHABET = "ABCDEFGHJKMNPQRSTUVWXYZ23456789"   # no 0/O, 1/I/L
_ADDR_RE = re.compile(r"[\w.+-]+@[\w-]+(?:\.[\w-]+)+")
CODE_RE = re.compile(r"AEGIS-([A-Z2-9]{6})(?![A-Z0-9])", re.I)
# the code plus brackets around it, removed from the subject shown in lists
_CODE_IN_SUBJECT = re.compile(r"\s*[\[(]?\s*AEGIS-[A-Z2-9]{6}(?![A-Z0-9])\s*[\])]?", re.I)


def strip_code(subject: str) -> str:
    """The subject to display: without the routing code, which means nothing to a reader
    (the stored email keeps it)."""
    return re.sub(r"\s{2,}", " ", _CODE_IN_SUBJECT.sub(" ", subject or "")).strip()


def _new_code() -> str:
    return "AEGIS-" + "".join(secrets.choice(_ALPHABET) for _ in range(6))


async def code_for(session, owner_hash: str) -> str:
    """This browser's code, created on first use."""
    row = (await session.execute(select(ViewerCode).where(
        ViewerCode.owner_hash == owner_hash))).scalar_one_or_none()
    if row:
        return row.code
    for _ in range(5):
        code = _new_code()
        try:
            async with session.begin_nested():
                session.add(ViewerCode(code=code, owner_hash=owner_hash))
            return code
        except IntegrityError:   # code collision, or a parallel request made one first
            row = (await session.execute(select(ViewerCode).where(
                ViewerCode.owner_hash == owner_hash))).scalar_one_or_none()
            if row:
                return row.code
    raise RuntimeError("could not allocate an inbox code")


async def owner_for(session, *texts: str) -> str | None:
    """The owner whose code appears first in the given texts (subject, then body)."""
    for text in texts:
        for m in CODE_RE.finditer(text or ""):
            owner = (await session.execute(select(ViewerCode.owner_hash).where(
                ViewerCode.code == "AEGIS-" + m.group(1).upper()))).scalar_one_or_none()
            if owner:
                return owner
    return None


def sender_key(sender: str | None) -> str | None:
    """Hash of the bare, lower-cased sender address (`Name <a@b.c>` -> a@b.c)."""
    m = _ADDR_RE.search(sender or "")
    return hashlib.sha256(m.group(0).lower().encode()).hexdigest() if m else None


async def resolve(session, subject: str, text: str, sender: str | None) -> str | None:
    """Owner of an inbox email: by its code (which also links the sender to that browser),
    else by a sender linked earlier."""
    key = sender_key(sender)
    owner = await owner_for(session, subject, text)
    if owner:
        if key:
            link = await session.get(SenderLink, key)
            if link is None:
                session.add(SenderLink(sender_hash=key, owner_hash=owner))
            else:
                link.owner_hash, link.updated_at = owner, datetime.now(timezone.utc)
        return owner
    if key:
        link = await session.get(SenderLink, key)
        return link.owner_hash if link else None
    return None
