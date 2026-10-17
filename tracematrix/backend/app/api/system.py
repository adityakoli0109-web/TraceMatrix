from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select, text
from sqlalchemy.orm import Session

from app.config import get_settings
from app.db import engine, get_db
from app.models import OsintSource, User
from app.schemas import SourceCreate
from app.security import get_current_user, require_roles
from app.services.access import write_audit
from app.services.blockchain import ProviderError, ProviderNotConfigured, integration_status, lookup
from app.services.jobs import create_job
from app.services.osint import github_status
from app.services.ssrf import FeedFetchError, validate_feed_url

router = APIRouter(tags=["system"])


@router.get("/health")
def health() -> dict:
    return {"status": "ok", "service": "tracematrix", "time": datetime.now(UTC).isoformat()}


@router.get("/ready")
def ready() -> dict:
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        return {"status": "ready"}
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=503, detail="Database not ready") from exc


@router.get("/api/v1/integrations")
def integrations(user: User = Depends(get_current_user)) -> dict:
    settings = get_settings()
    chain = integration_status()
    github = github_status()
    feeds = "configured" if settings.feed_allowlist else "not_configured"
    redis = "configured" if settings.redis_url else "in_process"
    return {
        "ethereum": chain,
        "github": github,
        "threat_feeds": {"status": feeds, "allowlist": sorted(settings.feed_allowlist)},
        "jobs": {"mode": redis},
    }


@router.get("/api/v1/explorer/lookup")
def explorer_lookup(q: str, user: User = Depends(get_current_user)) -> dict:
    try:
        result = lookup(q.strip())
    except ProviderNotConfigured as exc:
        return {"status": "not_configured", "error": str(exc), "integrations": integration_status()}
    except ProviderError as exc:
        return {"status": "error", "error": str(exc), "integrations": integration_status()}
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"status": "ok", "result": result}


@router.get("/api/v1/osint/sources")
def list_sources(db: Session = Depends(get_db), user: User = Depends(get_current_user)) -> dict:
    rows = db.scalars(select(OsintSource).order_by(OsintSource.created_at.desc())).all()
    return {
        "items": [
            {
                "id": r.id,
                "name": r.name,
                "source_type": r.source_type,
                "endpoint": r.endpoint,
                "enabled": r.enabled,
                "status": r.status,
                "last_success_at": r.last_success_at,
                "last_error": r.last_error,
            }
            for r in rows
        ]
    }


@router.post("/api/v1/osint/sources", status_code=201)
def create_source(
    payload: SourceCreate,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles("admin", "analyst")),
) -> dict:
    if payload.source_type == "threat_feed":
        try:
            validate_feed_url(payload.endpoint)
        except FeedFetchError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
    row = OsintSource(
        name=payload.name,
        source_type=payload.source_type,
        endpoint=payload.endpoint,
        enabled=payload.enabled,
        status="configured",
        config=payload.config,
    )
    db.add(row)
    write_audit(db, actor_id=user.id, action="osint.source.create", details={"name": payload.name})
    db.commit()
    db.refresh(row)
    return {"id": row.id, "status": row.status}


@router.post("/api/v1/osint/sources/{source_id}/refresh")
def refresh_source(
    source_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles("admin", "analyst")),
) -> dict:
    source = db.get(OsintSource, source_id)
    if source is None:
        raise HTTPException(status_code=404, detail="Source not found")
    job = create_job(db, investigation_id=None, job_type="ingest_osint", user_id=user.id, extra={"source_id": source_id})
    return {"job_id": job.id, "note": "OSINT refresh requires an investigation context for evidence persistence. Use case workspace ingest for evidence."}
