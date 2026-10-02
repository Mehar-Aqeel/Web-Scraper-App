"""Persistence helpers for scraping history (TICKET-027/028)."""
from __future__ import annotations

import time
from typing import Any

from sqlalchemy import desc, func, select

from app.models.history import ScrapedRecord, ScrapingJob
from app.services.database import AsyncSessionLocal


async def save_job(
    url: str,
    fields: list[str],
    records: list[dict[str, Any]],
    warnings: list[str],
    duration_ms: float,
    used_js: bool = False,
) -> int:
    """Persist a completed extraction job and its records. Returns the job id."""
    async with AsyncSessionLocal() as session:
        job = ScrapingJob(
            url=url,
            fields=",".join(fields),
            status="done",
            record_count=len(records),
            warning_count=len(warnings),
            duration_ms=duration_ms,
            created_at=time.time(),
            used_js=int(used_js),
        )
        session.add(job)
        await session.flush()  # get job.id

        for row in records:
            extra = {k: v for k, v in row.items() if k not in ("type", "value", "source_url")}
            session.add(ScrapedRecord(
                job_id=job.id,
                type=row.get("type", ""),
                value=str(row.get("value", "")) if row.get("value") is not None else None,
                extra=extra or None,
                source_url=row.get("source_url"),
            ))

        await session.commit()
        return job.id


async def list_jobs(limit: int = 50) -> list[dict]:
    """Return the most recent scraping jobs."""
    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(ScrapingJob).order_by(desc(ScrapingJob.created_at)).limit(limit)
        )
        jobs = result.scalars().all()
        return [
            {
                "id": j.id,
                "url": j.url,
                "fields": j.fields.split(","),
                "status": j.status,
                "record_count": j.record_count,
                "warning_count": j.warning_count,
                "duration_ms": j.duration_ms,
                "created_at": j.created_at,
                "used_js": bool(j.used_js),
            }
            for j in jobs
        ]


async def get_job_records(job_id: int) -> list[dict]:
    """Return all records for a given job."""
    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(ScrapedRecord).where(ScrapedRecord.job_id == job_id)
        )
        rows = result.scalars().all()
        return [
            {
                "type": r.type,
                "value": r.value,
                **(r.extra or {}),
                "source_url": r.source_url,
            }
            for r in rows
        ]


async def get_dashboard_stats() -> dict:
    """Return aggregate stats across all jobs."""
    async with AsyncSessionLocal() as session:
        total_jobs = (await session.execute(func.count(ScrapingJob.id).select())).scalar() or 0
        total_records = (await session.execute(func.count(ScrapedRecord.id).select())).scalar() or 0
        avg_duration = (await session.execute(func.avg(ScrapingJob.duration_ms).select())).scalar() or 0.0

        type_counts_result = await session.execute(
            select(ScrapedRecord.type, func.count(ScrapedRecord.id))
            .group_by(ScrapedRecord.type)
        )
        type_counts = {row[0]: row[1] for row in type_counts_result.all()}

        return {
            "total_jobs": total_jobs,
            "total_records": total_records,
            "avg_duration_ms": round(avg_duration, 1),
            "records_by_type": type_counts,
        }
