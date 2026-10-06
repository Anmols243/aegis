"""In-process pub/sub for live analysis progress (feeds the SSE endpoint)."""
from __future__ import annotations

import asyncio
from collections import defaultdict


class EventBus:
    def __init__(self) -> None:
        self._subs: dict[str, set[asyncio.Queue]] = defaultdict(set)

    def subscribe(self, topic: str) -> asyncio.Queue:
        q: asyncio.Queue = asyncio.Queue(maxsize=256)
        self._subs[topic].add(q)
        return q

    def unsubscribe(self, topic: str, q: asyncio.Queue) -> None:
        subs = self._subs.get(topic)
        if subs is not None:
            subs.discard(q)
            if not subs:
                self._subs.pop(topic, None)

    def publish(self, topic: str, event: str, data: dict) -> None:
        for q in list(self._subs.get(topic, ())):
            try:
                q.put_nowait((event, data))
            except asyncio.QueueFull:
                pass  # a stalled client misses events; it can refetch the analysis


bus = EventBus()
