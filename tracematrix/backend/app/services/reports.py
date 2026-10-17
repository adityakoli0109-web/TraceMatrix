from __future__ import annotations

import csv
import io
import json
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import (
    AnalysisResult,
    CandidateLink,
    ChainTransaction,
    GraphEdge,
    Investigation,
    OsintEvidence,
    ReportExport,
)


def _csv_safe(value: str) -> str:
    text = "" if value is None else str(value)
    if text[:1] in {"=", "+", "-", "@", "\t"}:
        return "'" + text
    return text


def build_report_payload(db: Session, investigation: Investigation) -> dict:
    evidence = db.scalars(select(OsintEvidence).where(OsintEvidence.investigation_id == investigation.id)).all()
    candidates = db.scalars(select(CandidateLink).where(CandidateLink.investigation_id == investigation.id)).all()
    edges = db.scalars(select(GraphEdge).where(GraphEdge.investigation_id == investigation.id)).all()
    analysis = db.scalar(
        select(AnalysisResult)
        .where(AnalysisResult.investigation_id == investigation.id)
        .order_by(AnalysisResult.id.desc())
    )
    txs = db.scalars(select(ChainTransaction).limit(5000)).all()
    related_hashes = {e.tx_hash for e in edges}
    related_txs = [t for t in txs if t.tx_hash in related_hashes]
    return {
        "title": investigation.title,
        "investigation_id": investigation.id,
        "generated_at": datetime.now(UTC).isoformat(),
        "is_fixture": investigation.is_fixture,
        "executive_summary": (
            f"Investigation '{investigation.title}' examined seed {investigation.seed_value} "
            f"with {len(related_txs)} ingested transactions and {len(evidence)} OSINT evidence records. "
            "Candidate scores are triage heuristics, not identity probabilities."
        ),
        "scope": {
            "seed": investigation.seed_value,
            "objective": investigation.objective,
            "max_depth": investigation.max_depth,
            "max_transactions": investigation.max_transactions,
            "date_from": investigation.date_from.isoformat() if investigation.date_from else None,
            "date_to": investigation.date_to.isoformat() if investigation.date_to else None,
        },
        "methodology": {
            "algorithm_version": analysis.payload.get("algorithm_version") if analysis else None,
            "notes": "Neighborhood ingestion from seed; OSINT connectors; explainable qce-1.0.0 scoring.",
        },
        "transactions": [
            {
                "tx_hash": t.tx_hash,
                "from": t.from_address,
                "to": t.to_address,
                "value_wei": str(t.value_wei),
                "timestamp": t.timestamp.isoformat() if t.timestamp else None,
                "is_fixture": t.is_fixture,
            }
            for t in related_txs
        ],
        "graph": {
            "edge_count": len(edges),
            "notice": "Connectivity does not prove common ownership.",
        },
        "osint": [
            {
                "id": e.id,
                "source_type": e.source_type,
                "source_url": e.source_url,
                "indicator": e.indicator,
                "collected_at": e.collected_at.isoformat() if e.collected_at else None,
                "original_timestamp": e.original_timestamp.isoformat() if e.original_timestamp else None,
                "verification_status": e.verification_status,
            }
            for e in evidence
        ],
        "candidates": [
            {
                "wallet": c.wallet_address,
                "label": c.label,
                "score": float(c.overall_score),
                "supporting": c.supporting,
                "contradictory": c.contradictory,
                "explanation": c.explanation,
                "verification_status": c.verification_status,
            }
            for c in candidates
        ],
        "limitations": [
            "Historical address activity requires an explorer API.",
            "OSINT text is untrusted and is not a verified identity claim.",
            "Missing provider credentials produce not_configured states rather than fabricated results.",
        ],
        "analysis": analysis.payload if analysis else None,
    }


def export_report(db: Session, investigation: Investigation, user_id: str, fmt: str) -> ReportExport:
    payload = build_report_payload(db, investigation)
    if fmt == "json":
        body = json.dumps(payload, indent=2)
    elif fmt == "csv":
        buf = io.StringIO()
        writer = csv.writer(buf)
        writer.writerow(["section", "field", "value"])
        writer.writerow(["meta", "title", _csv_safe(payload["title"])])
        writer.writerow(["meta", "seed", _csv_safe(payload["scope"]["seed"])])
        for tx in payload["transactions"]:
            writer.writerow(["transaction", _csv_safe(tx["tx_hash"]), _csv_safe(tx["from"] + "->" + (tx["to"] or ""))])
        for item in payload["osint"]:
            writer.writerow(["osint", _csv_safe(item["indicator"]), _csv_safe(item["source_url"])])
        for cand in payload["candidates"]:
            writer.writerow(["candidate", _csv_safe(cand["wallet"]), _csv_safe(cand["label"])])
        body = buf.getvalue()
    elif fmt == "html":
        body = _html_report(payload)
    else:
        raise ValueError("Unsupported format")
    row = ReportExport(investigation_id=investigation.id, created_by=user_id, format=fmt, body=body)
    db.add(row)
    db.flush()
    return row


def _html_report(payload: dict) -> str:
    fixture_banner = (
        "<p><strong>Demo fixture — not live blockchain data.</strong></p>" if payload.get("is_fixture") else ""
    )
    candidates = "".join(
        f"<li><code>{c['wallet']}</code> — {c['label']} (heuristic {c['score']})</li>" for c in payload["candidates"]
    )
    return f"""<!DOCTYPE html>
<html><head><meta charset="utf-8"><title>TraceMatrix Report</title>
<style>body{{font-family:IBM Plex Sans,Segoe UI,sans-serif;color:#1c2430;max-width:900px;margin:40px auto;}}
h1{{font-size:20px}} table{{border-collapse:collapse;width:100%}} td,th{{border:1px solid #d8dde6;padding:6px;font-size:13px}}</style>
</head><body>
<h1>TraceMatrix investigation report</h1>
{fixture_banner}
<p>{payload['executive_summary']}</p>
<h2>Scope</h2>
<p>Seed: {payload['scope']['seed']}</p>
<h2>Candidate links</h2>
<ul>{candidates or "<li>Insufficient evidence.</li>"}</ul>
<h2>Limitations</h2>
<ul>{''.join(f"<li>{item}</li>" for item in payload["limitations"])}</ul>
<p>Generated at {payload['generated_at']}</p>
</body></html>"""
