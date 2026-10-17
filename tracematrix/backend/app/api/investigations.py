from datetime import UTC, datetime
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.db import get_db
from app.ethutil import classify_seed, normalize_address, to_checksum_address
from app.models import (
    AnalystNote,
    AuditLog,
    CandidateLink,
    CandidateReview,
    ChainTransaction,
    GraphEdge,
    IngestionJob,
    Investigation,
    InvestigationMember,
    InvestigationWallet,
    OsintEvidence,
    User,
    Wallet,
)
from app.schemas import InvestigationCreate, InvestigationUpdate, NoteCreate, ReviewCreate
from app.security import get_current_user, require_roles
from app.services.access import get_investigation_for_user, write_audit
from app.services.analysis import shortest_path, build_graph, graph_metrics
from app.services.jobs import create_job
from app.services.reports import export_report

router = APIRouter(prefix="/api/v1", tags=["investigations"])


def _serialize_inv(inv: Investigation) -> dict[str, Any]:
    return {
        "id": inv.id,
        "title": inv.title,
        "description": inv.description,
        "seed_value": inv.seed_value,
        "seed_type": inv.seed_type,
        "objective": inv.objective,
        "status": inv.status,
        "date_from": inv.date_from,
        "date_to": inv.date_to,
        "max_depth": inv.max_depth,
        "max_transactions": inv.max_transactions,
        "selected_sources": inv.selected_sources,
        "is_fixture": inv.is_fixture,
        "created_at": inv.created_at,
        "updated_at": inv.updated_at,
        "archived_at": inv.archived_at,
    }


@router.get("/dashboard")
def dashboard(db: Session = Depends(get_db), user: User = Depends(get_current_user)) -> dict[str, Any]:
    total = db.scalar(select(func.count(Investigation.id))) or 0
    active = db.scalar(select(func.count(Investigation.id)).where(Investigation.status == "active")) or 0
    completed = db.scalar(select(func.count(Investigation.id)).where(Investigation.status == "completed")) or 0
    wallets = db.scalar(select(func.count(Wallet.id))) or 0
    txs = db.scalar(select(func.count(ChainTransaction.id))) or 0
    jobs = db.scalars(select(IngestionJob).order_by(IngestionJob.created_at.desc()).limit(8)).all()
    recent = db.scalars(select(Investigation).order_by(Investigation.created_at.desc()).limit(8)).all()
    return {
        "totals": {
            "investigations": total,
            "active": active,
            "completed": completed,
            "wallets": wallets,
            "transactions": txs,
        },
        "jobs": [
            {
                "id": j.id,
                "job_type": j.job_type,
                "status": j.status,
                "progress": j.progress,
                "message": j.message,
                "investigation_id": j.investigation_id,
                "created_at": j.created_at,
            }
            for j in jobs
        ],
        "recent": [_serialize_inv(i) for i in recent],
        "empty": total == 0,
    }


@router.get("/investigations")
def list_investigations(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    q: str | None = None,
    status: str | None = None,
    sort: str = "created_at",
    order: str = "desc",
) -> dict[str, Any]:
    stmt = select(Investigation).where(Investigation.archived_at.is_(None))
    if q:
        like = f"%{q}%"
        stmt = stmt.where(or_(Investigation.title.like(like), Investigation.seed_value.like(like)))
    if status:
        stmt = stmt.where(Investigation.status == status)
    sort_col = getattr(Investigation, sort, Investigation.created_at)
    stmt = stmt.order_by(sort_col.asc() if order == "asc" else sort_col.desc())
    total = db.scalar(select(func.count()).select_from(stmt.subquery())) or 0
    items = db.scalars(stmt.offset((page - 1) * page_size).limit(page_size)).all()
    return {"items": [_serialize_inv(i) for i in items], "total": total, "page": page, "page_size": page_size}


@router.post("/investigations")
def create_investigation(
    payload: InvestigationCreate,
    response: Response,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles("analyst", "admin")),
) -> dict[str, Any]:
    try:
        seed_type = payload.seed_type()
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    if not payload.confirm_scope:
        return {
            "confirmation_required": True,
            "scope": {
                "title": payload.title,
                "seed_value": payload.seed_value,
                "seed_type": seed_type,
                "max_depth": payload.max_depth,
                "max_transactions": payload.max_transactions,
                "notice": (
                    "Ingestion is bounded by max depth and transaction limits. "
                    "This will not download the full Ethereum chain. "
                    "Address history requires an explorer API."
                ),
            },
        }
    seed = payload.seed_value.strip()
    if seed_type == "address":
        seed = normalize_address(seed)
    inv = Investigation(
        title=payload.title,
        description=payload.description,
        seed_value=seed,
        seed_type=seed_type,
        objective=payload.objective,
        date_from=payload.date_from,
        date_to=payload.date_to,
        max_depth=payload.max_depth,
        max_transactions=payload.max_transactions,
        selected_sources=payload.selected_sources,
        created_by=user.id,
        status="active",
    )
    db.add(inv)
    db.flush()
    db.add(InvestigationMember(investigation_id=inv.id, user_id=user.id, member_role="owner"))
    response.status_code = 201
    write_audit(db, actor_id=user.id, action="investigation.create", investigation_id=inv.id, details={"title": inv.title})
    db.commit()
    db.refresh(inv)
    job = create_job(db, investigation_id=inv.id, job_type="full_pipeline", user_id=user.id)
    return {"investigation": _serialize_inv(inv), "job_id": job.id}


@router.get("/investigations/{investigation_id}")
def get_investigation(
    investigation_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> dict[str, Any]:
    inv = get_investigation_for_user(db, investigation_id, user)
    return _serialize_inv(inv)


@router.patch("/investigations/{investigation_id}")
def update_investigation(
    investigation_id: str,
    payload: InvestigationUpdate,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles("analyst", "admin")),
) -> dict[str, Any]:
    inv = get_investigation_for_user(db, investigation_id, user)
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(inv, field, value)
    write_audit(db, actor_id=user.id, action="investigation.update", investigation_id=inv.id)
    db.commit()
    db.refresh(inv)
    return _serialize_inv(inv)


@router.post("/investigations/{investigation_id}/archive")
def archive_investigation(
    investigation_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles("analyst", "admin")),
) -> dict[str, Any]:
    inv = get_investigation_for_user(db, investigation_id, user)
    inv.archived_at = datetime.now(UTC)
    inv.status = "archived"
    write_audit(db, actor_id=user.id, action="investigation.archive", investigation_id=inv.id)
    db.commit()
    return _serialize_inv(inv)


@router.post("/investigations/{investigation_id}/jobs/{job_type}")
def start_job(
    investigation_id: str,
    job_type: str,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles("analyst", "admin")),
) -> dict[str, Any]:
    get_investigation_for_user(db, investigation_id, user)
    if job_type not in {"ingest_chain", "ingest_osint", "analyze", "full_pipeline"}:
        raise HTTPException(status_code=400, detail="Unsupported job type")
    job = create_job(db, investigation_id=investigation_id, job_type=job_type, user_id=user.id)
    return {"job_id": job.id, "status": job.status}


@router.get("/jobs/{job_id}")
def get_job(job_id: str, db: Session = Depends(get_db), user: User = Depends(get_current_user)) -> dict[str, Any]:
    job = db.get(IngestionJob, job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found")
    if job.investigation_id:
        get_investigation_for_user(db, job.investigation_id, user)
    return {
        "id": job.id,
        "status": job.status,
        "progress": job.progress,
        "message": job.message,
        "error": job.error,
        "job_type": job.job_type,
        "extra": job.extra,
        "investigation_id": job.investigation_id,
    }


@router.post("/jobs/{job_id}/cancel")
def cancel_job(job_id: str, db: Session = Depends(get_db), user: User = Depends(require_roles("analyst", "admin"))) -> dict[str, Any]:
    job = db.get(IngestionJob, job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found")
    if job.investigation_id:
        get_investigation_for_user(db, job.investigation_id, user)
    job.cancel_requested = True
    if job.status == "queued":
        job.status = "cancelled"
        job.finished_at = datetime.now(UTC)
    db.commit()
    return {"id": job.id, "status": job.status, "cancel_requested": True}


@router.get("/investigations/{investigation_id}/transactions")
def list_tx(
    investigation_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
    page: int = 1,
    page_size: int = 25,
    address: str | None = None,
    min_wei: str | None = None,
) -> dict[str, Any]:
    get_investigation_for_user(db, investigation_id, user)
    edges = db.scalars(select(GraphEdge).where(GraphEdge.investigation_id == investigation_id)).all()
    hashes = {e.tx_hash for e in edges}
    stmt = select(ChainTransaction).where(ChainTransaction.tx_hash.in_(hashes or {"__none__"}))
    if address:
        addr = address.lower()
        stmt = stmt.where(or_(ChainTransaction.from_address == addr, ChainTransaction.to_address == addr))
    rows = db.scalars(stmt.order_by(ChainTransaction.timestamp.desc())).all()
    if min_wei:
        rows = [r for r in rows if int(r.value_wei or 0) >= int(min_wei)]
    total = len(rows)
    sliced = rows[(page - 1) * page_size : page * page_size]
    return {
        "total": total,
        "items": [
            {
                "tx_hash": r.tx_hash,
                "block_number": r.block_number,
                "timestamp": r.timestamp,
                "from_address": r.from_address,
                "to_address": r.to_address,
                "value_wei": str(r.value_wei),
                "status": r.status,
                "gas_used": r.gas_used,
                "is_fixture": r.is_fixture,
            }
            for r in sliced
        ],
        "page": page,
        "page_size": page_size,
    }


@router.get("/investigations/{investigation_id}/graph")
def get_graph(
    investigation_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
    max_nodes: int = Query(200, le=400),
) -> dict[str, Any]:
    get_investigation_for_user(db, investigation_id, user)
    edges = db.scalars(select(GraphEdge).where(GraphEdge.investigation_id == investigation_id)).all()
    graph = build_graph(edges)
    metrics = graph_metrics(graph)
    nodes = metrics["nodes"][:max_nodes]
    allowed = {n["address"] for n in nodes}
    cy_edges = []
    for edge in edges:
        if edge.from_address in allowed and edge.to_address in allowed:
            cy_edges.append(
                {
                    "id": edge.id,
                    "source": edge.from_address,
                    "target": edge.to_address,
                    "tx_hash": edge.tx_hash,
                    "value_wei": str(edge.value_raw),
                    "token": edge.token_address,
                    "timestamp": edge.timestamp.isoformat() if edge.timestamp else None,
                }
            )
    community_map = {}
    for idx, comm in enumerate(metrics["communities"]):
        for addr in comm:
            community_map[addr] = idx
    for node in nodes:
        node["community"] = community_map.get(node["address"], 0)
        node["checksum"] = to_checksum_address(node["address"]) if node["address"].startswith("0x") else node["address"]
    return {
        "nodes": nodes,
        "edges": cy_edges,
        "truncated": len(metrics["nodes"]) > max_nodes,
        "notice": "Graph connectivity does not prove common ownership.",
        "communities": metrics["communities"],
    }


@router.get("/investigations/{investigation_id}/graph/path")
def graph_path(
    investigation_id: str,
    source: str,
    target: str,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> dict[str, Any]:
    get_investigation_for_user(db, investigation_id, user)
    edges = db.scalars(select(GraphEdge).where(GraphEdge.investigation_id == investigation_id)).all()
    path = shortest_path(build_graph(edges), source, target)
    return {"path": path, "found": bool(path)}


@router.get("/investigations/{investigation_id}/evidence")
def list_evidence(
    investigation_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
    q: str | None = None,
) -> dict[str, Any]:
    get_investigation_for_user(db, investigation_id, user)
    stmt = select(OsintEvidence).where(OsintEvidence.investigation_id == investigation_id)
    if q:
        stmt = stmt.where(or_(OsintEvidence.indicator.like(f"%{q}%"), OsintEvidence.source_url.like(f"%{q}%")))
    rows = db.scalars(stmt.order_by(OsintEvidence.collected_at.desc())).all()
    return {
        "items": [
            {
                "id": r.id,
                "source_type": r.source_type,
                "source_url": r.source_url,
                "source_record_id": r.source_record_id,
                "indicator": r.indicator,
                "original_timestamp": r.original_timestamp,
                "collected_at": r.collected_at,
                "extracted_context": r.extracted_context,
                "extraction_method": r.extraction_method,
                "verification_status": r.verification_status,
                "reliability": r.reliability,
                "notice": "Unverified public text. Not an identity claim.",
            }
            for r in rows
        ]
    }


@router.get("/investigations/{investigation_id}/candidates")
def list_candidates(
    investigation_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> dict[str, Any]:
    get_investigation_for_user(db, investigation_id, user)
    rows = db.scalars(
        select(CandidateLink).where(CandidateLink.investigation_id == investigation_id).order_by(CandidateLink.overall_score.desc())
    ).all()
    return {
        "items": [
            {
                "id": r.id,
                "wallet_address": r.wallet_address,
                "relationship_type": r.relationship_type,
                "supporting": r.supporting,
                "contradictory": r.contradictory,
                "temporal_score": float(r.temporal_score),
                "graph_score": float(r.graph_score),
                "reliability_score": float(r.reliability_score),
                "overall_score": float(r.overall_score),
                "label": r.label,
                "explanation": r.explanation,
                "evidence_ids": r.evidence_ids,
                "component_scores": r.component_scores,
                "verification_status": r.verification_status,
                "analysis_timestamp": r.analysis_timestamp,
            }
            for r in rows
        ],
        "disclaimer": "Heuristic triage scores, not identity probabilities.",
    }


@router.post("/candidates/{candidate_id}/review")
def review_candidate(
    candidate_id: str,
    payload: ReviewCreate,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles("analyst", "admin")),
) -> dict[str, Any]:
    cand = db.get(CandidateLink, candidate_id)
    if cand is None:
        raise HTTPException(status_code=404, detail="Candidate not found")
    get_investigation_for_user(db, cand.investigation_id, user)
    cand.verification_status = payload.decision
    db.add(CandidateReview(candidate_id=cand.id, reviewer_id=user.id, decision=payload.decision, rationale=payload.rationale))
    write_audit(
        db,
        actor_id=user.id,
        action="candidate.review",
        investigation_id=cand.investigation_id,
        details={"decision": payload.decision, "notice": "Analyst confirmation is not blockchain identity verification."},
    )
    db.commit()
    return {"id": cand.id, "verification_status": cand.verification_status}


@router.get("/investigations/{investigation_id}/notes")
def list_notes(
    investigation_id: str, db: Session = Depends(get_db), user: User = Depends(get_current_user)
) -> dict[str, Any]:
    get_investigation_for_user(db, investigation_id, user)
    rows = db.scalars(select(AnalystNote).where(AnalystNote.investigation_id == investigation_id)).all()
    return {"items": [{"id": r.id, "body": r.body, "author_id": r.author_id, "created_at": r.created_at} for r in rows]}


@router.post("/investigations/{investigation_id}/notes")
def add_note(
    investigation_id: str,
    payload: NoteCreate,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles("analyst", "admin")),
) -> dict[str, Any]:
    get_investigation_for_user(db, investigation_id, user)
    note = AnalystNote(investigation_id=investigation_id, author_id=user.id, body=payload.body)
    db.add(note)
    write_audit(db, actor_id=user.id, action="note.create", investigation_id=investigation_id)
    db.commit()
    db.refresh(note)
    return {"id": note.id, "body": note.body, "created_at": note.created_at}


@router.get("/investigations/{investigation_id}/audit")
def list_audit(
    investigation_id: str, db: Session = Depends(get_db), user: User = Depends(get_current_user)
) -> dict[str, Any]:
    get_investigation_for_user(db, investigation_id, user)
    rows = db.scalars(
        select(AuditLog).where(AuditLog.investigation_id == investigation_id).order_by(AuditLog.created_at.desc())
    ).all()
    return {
        "items": [
            {"id": r.id, "action": r.action, "actor_id": r.actor_id, "details": r.details, "created_at": r.created_at}
            for r in rows
        ]
    }


@router.get("/investigations/{investigation_id}/timeline")
def timeline(
    investigation_id: str, db: Session = Depends(get_db), user: User = Depends(get_current_user)
) -> dict[str, Any]:
    get_investigation_for_user(db, investigation_id, user)
    events = []
    for edge in db.scalars(select(GraphEdge).where(GraphEdge.investigation_id == investigation_id)).all():
        events.append(
            {
                "kind": "transaction",
                "source_timestamp": edge.timestamp,
                "collected_timestamp": None,
                "label": f"{edge.from_address} → {edge.to_address}",
                "ref": edge.tx_hash,
            }
        )
    for ev in db.scalars(select(OsintEvidence).where(OsintEvidence.investigation_id == investigation_id)).all():
        events.append(
            {
                "kind": "osint",
                "source_timestamp": ev.original_timestamp,
                "collected_timestamp": ev.collected_at,
                "label": f"{ev.source_type}: {ev.indicator or ev.source_url}",
                "ref": ev.source_url,
            }
        )
    for job in db.scalars(select(IngestionJob).where(IngestionJob.investigation_id == investigation_id)).all():
        events.append(
            {
                "kind": "ingestion",
                "source_timestamp": job.started_at,
                "collected_timestamp": job.created_at,
                "label": f"Job {job.job_type} {job.status}",
                "ref": job.id,
            }
        )
    for log in db.scalars(select(AuditLog).where(AuditLog.investigation_id == investigation_id)).all():
        events.append(
            {
                "kind": "analyst",
                "source_timestamp": log.created_at,
                "collected_timestamp": log.created_at,
                "label": log.action,
                "ref": log.id,
            }
        )
    events.sort(key=lambda e: e["source_timestamp"] or e["collected_timestamp"] or datetime.min.replace(tzinfo=UTC))
    return {"items": events}


@router.get("/investigations/{investigation_id}/analysis")
def get_analysis(
    investigation_id: str, db: Session = Depends(get_db), user: User = Depends(get_current_user)
) -> dict[str, Any]:
    get_investigation_for_user(db, investigation_id, user)
    from app.models import AnalysisResult

    row = db.scalar(
        select(AnalysisResult)
        .where(AnalysisResult.investigation_id == investigation_id)
        .order_by(AnalysisResult.id.desc())
    )
    if row is None:
        return {"payload": None}
    return {"id": row.id, "run_id": row.run_id, "payload": row.payload}


@router.post("/investigations/{investigation_id}/reports/{fmt}")
def create_report(
    investigation_id: str,
    fmt: str,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles("analyst", "admin")),
) -> dict[str, Any]:
    inv = get_investigation_for_user(db, investigation_id, user)
    if fmt not in {"json", "csv", "html"}:
        raise HTTPException(status_code=400, detail="Unsupported format")
    row = export_report(db, inv, user.id, fmt)
    write_audit(db, actor_id=user.id, action="report.export", investigation_id=inv.id, details={"format": fmt})
    db.commit()
    return {"id": row.id, "format": row.format, "body": row.body}
