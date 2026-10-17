from __future__ import annotations

import logging
import threading
import traceback
from datetime import UTC, datetime
from typing import Any, Callable

from sqlalchemy.orm import Session

from app.config import get_settings
from app.db import SessionLocal
from app.models import IngestionJob, Investigation
from app.services.analysis import analyze_investigation
from app.services.ingest import ingest_for_investigation
from app.services.osint import ingest_osint

logger = logging.getLogger(__name__)
_lock = threading.Lock()


def _rq_queue():
    settings = get_settings()
    if not settings.redis_url:
        return None
    try:
        from redis import Redis
        from rq import Queue

        return Queue("tracematrix", connection=Redis.from_url(settings.redis_url), default_timeout=settings.job_timeout_seconds)
    except Exception as exc:  # noqa: BLE001
        logger.warning("Redis unavailable, falling back to in-process jobs: %s", exc)
        return None


def create_job(db: Session, *, investigation_id: str | None, job_type: str, user_id: str | None, extra: dict | None = None) -> IngestionJob:
    job = IngestionJob(
        investigation_id=investigation_id,
        job_type=job_type,
        status="queued",
        created_by=user_id,
        extra=extra or {},
    )
    db.add(job)
    db.commit()
    db.refresh(job)
    enqueue_job(job.id)
    return job


def enqueue_job(job_id: str) -> None:
    settings = get_settings()
    if settings.sync_jobs:
        run_job(job_id)
        return
    queue = _rq_queue()
    if queue is not None:
        queue.enqueue(run_job, job_id, job_id=job_id)
        return

    thread = threading.Thread(target=run_job, args=(job_id,), daemon=True)
    thread.start()


def run_job(job_id: str) -> None:
    with _lock:
        db = SessionLocal()
        try:
            job = db.get(IngestionJob, job_id)
            if job is None or job.status in {"cancelled", "success"}:
                return
            if job.cancel_requested:
                job.status = "cancelled"
                job.finished_at = datetime.now(UTC)
                db.commit()
                return
            job.status = "running"
            job.started_at = datetime.now(UTC)
            job.progress = 5
            db.commit()
            _execute(db, job)
            if job.cancel_requested:
                job.status = "cancelled"
            else:
                job.status = "success"
                job.progress = 100
            job.finished_at = datetime.now(UTC)
            db.commit()
        except Exception as exc:  # noqa: BLE001
            logger.exception("Job %s failed", job_id)
            job = db.get(IngestionJob, job_id)
            if job:
                job.status = "failed"
                job.error = str(exc)
                job.message = "Job failed"
                job.finished_at = datetime.now(UTC)
                db.commit()
        finally:
            db.close()


def _execute(db: Session, job: IngestionJob) -> None:
    inv = db.get(Investigation, job.investigation_id) if job.investigation_id else None

    def cancel_check() -> bool:
        db.refresh(job)
        return bool(job.cancel_requested)

    if job.job_type == "ingest_chain":
        if inv is None:
            raise RuntimeError("Investigation missing")
        job.message = "Ingesting blockchain neighborhood"
        db.commit()
        result = ingest_for_investigation(db, inv, cancel_check=cancel_check)
        job.extra = {**(job.extra or {}), **result}
        job.progress = 70
        db.commit()
    elif job.job_type == "ingest_osint":
        if inv is None:
            raise RuntimeError("Investigation missing")
        job.message = "Collecting public OSINT"
        result = ingest_osint(db, inv)
        job.extra = {**(job.extra or {}), **result}
        job.progress = 80
        db.commit()
    elif job.job_type == "analyze":
        if inv is None:
            raise RuntimeError("Investigation missing")
        job.message = "Running quantitative correlation engine"
        result = analyze_investigation(db, inv.id, user_id=job.created_by)
        job.extra = {**(job.extra or {}), "run_id": result["run_id"]}
        job.progress = 90
        db.commit()
    elif job.job_type == "full_pipeline":
        if inv is None:
            raise RuntimeError("Investigation missing")
        job.message = "Ingesting chain data"
        db.commit()
        chain = ingest_for_investigation(db, inv, cancel_check=cancel_check)
        job.progress = 40
        job.message = "Collecting OSINT"
        db.commit()
        osint = ingest_osint(db, inv)
        job.progress = 70
        job.message = "Analyzing"
        db.commit()
        analysis = analyze_investigation(db, inv.id, user_id=job.created_by)
        job.extra = {**(job.extra or {}), "chain": chain, "osint": osint, "run_id": analysis["run_id"]}
        if inv.status == "active":
            inv.status = "completed" if chain.get("ingested_transactions", 0) else "active"
        db.commit()
    else:
        raise RuntimeError(f"Unknown job type {job.job_type}")
