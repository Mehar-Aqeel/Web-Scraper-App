"""In-memory async job store for Playwright extraction jobs.

Each job tracks: status, stage label, progress %, result data, warnings, error.
Jobs are kept for JOB_TTL_SECONDS after completion then evicted on next access.
"""
from __future__ import annotations

import asyncio
import time
import uuid
from dataclasses import dataclass, field
from typing import Any

JOB_TTL_SECONDS = 300  # 5 minutes


@dataclass
class Job:
    job_id: str
    status: str = "pending"          # pending | running | done | error
    stage: str = "queued"
    progress: int = 0
    data: list[dict[str, Any]] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    error: str | None = None
    url: str = ""
    created_at: float = field(default_factory=time.time)
    finished_at: float | None = None
    # Subscribers waiting for progress updates via WebSocket
    _subscribers: list[asyncio.Queue] = field(default_factory=list, repr=False)

    def push(self, stage: str, progress: int) -> None:
        self.stage = stage
        self.progress = progress
        for q in self._subscribers:
            q.put_nowait({"stage": stage, "progress": progress, "status": self.status})

    def subscribe(self) -> asyncio.Queue:
        q: asyncio.Queue = asyncio.Queue()
        self._subscribers.append(q)
        return q

    def unsubscribe(self, q: asyncio.Queue) -> None:
        self._subscribers.discard(q) if hasattr(self._subscribers, "discard") else None
        try:
            self._subscribers.remove(q)
        except ValueError:
            pass


_store: dict[str, Job] = {}


def create_job(url: str) -> Job:
    job = Job(job_id=str(uuid.uuid4()), url=url)
    _store[job.job_id] = job
    _evict_expired()
    return job


def get_job(job_id: str) -> Job | None:
    return _store.get(job_id)


def _evict_expired() -> None:
    now = time.time()
    expired = [
        jid for jid, j in _store.items()
        if j.finished_at and (now - j.finished_at) > JOB_TTL_SECONDS
    ]
    for jid in expired:
        del _store[jid]
