from __future__ import annotations

import csv
import hashlib
import io
import json
from datetime import UTC, datetime
from typing import Any

import httpx
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.ethutil import extract_addresses
from app.models import Investigation, OsintEvidence, OsintSource
from app.services.ssrf import FeedFetchError, fetch_public_url


def github_status() -> dict[str, Any]:
    settings = get_settings()
    return {
        "configured": True,
        "authenticated": bool(settings.github_token),
        "rate_limit_note": "Unauthenticated GitHub search is limited to 10 requests/minute; a token raises the limit.",
        "base": settings.github_api_base,
    }


def _headers() -> dict[str, str]:
    settings = get_settings()
    headers = {"Accept": "application/vnd.github+json", "User-Agent": "TraceMatrix-OSINT"}
    if settings.github_token:
        headers["Authorization"] = f"Bearer {settings.github_token}"
    return headers


def search_github(keywords: list[str], *, per_page: int = 5) -> list[dict[str, Any]]:
    settings = get_settings()
    query = " ".join(keywords) + " 0x"
    url = f"{settings.github_api_base}/search/code"
    try:
        with httpx.Client(timeout=20.0) as client:
            response = client.get(
                url,
                params={"q": query, "per_page": per_page},
                headers=_headers(),
            )
            if response.status_code == 401:
                # code search often requires a token; fall back to repo search
                response = client.get(
                    f"{settings.github_api_base}/search/repositories",
                    params={"q": " ".join(keywords), "per_page": per_page},
                    headers=_headers(),
                )
            if response.status_code == 403:
                raise RuntimeError("GitHub rate limit reached. Configure GITHUB_TOKEN or retry later.")
            response.raise_for_status()
            payload = response.json()
    except httpx.HTTPError as exc:
        raise RuntimeError(f"GitHub request failed: {exc}") from exc
    items = payload.get("items") or []
    findings: list[dict[str, Any]] = []
    for item in items:
        html_url = item.get("html_url") or item.get("url") or ""
        text = json.dumps(item)[:4000]
        for address in extract_addresses(text):
            findings.append(
                {
                    "source_type": "github",
                    "source_url": html_url,
                    "source_record_id": str(item.get("sha") or item.get("id") or html_url),
                    "indicator": address,
                    "original_timestamp": item.get("updated_at") or item.get("pushed_at"),
                    "extracted_context": text[:500],
                    "extraction_method": "github_search_json_regex",
                    "reliability": "unverified_public_text",
                }
            )
        if not extract_addresses(text):
            findings.append(
                {
                    "source_type": "github",
                    "source_url": html_url,
                    "source_record_id": str(item.get("sha") or item.get("id") or html_url),
                    "indicator": "",
                    "original_timestamp": item.get("updated_at") or item.get("pushed_at"),
                    "extracted_context": (item.get("description") or item.get("name") or text)[:500],
                    "extraction_method": "github_search_metadata",
                    "reliability": "unverified_public_text",
                }
            )
    return findings


def parse_feed(body: str, content_type: str, source_url: str) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    if "json" in content_type or body.lstrip().startswith(("{", "[")):
        data = json.loads(body)
        rows = data if isinstance(data, list) else data.get("data") or data.get("items") or [data]
        for row in rows:
            text = json.dumps(row)
            for address in extract_addresses(text):
                records.append(
                    {
                        "source_type": "threat_feed",
                        "source_url": source_url,
                        "source_record_id": str(row.get("id") or row.get("uuid") or address),
                        "indicator": address,
                        "original_timestamp": row.get("published") or row.get("timestamp") or row.get("date"),
                        "extracted_context": text[:500],
                        "extraction_method": "json_feed_regex",
                        "reliability": "feed_unverified",
                    }
                )
        return records
    reader = csv.DictReader(io.StringIO(body))
    for row in reader:
        text = json.dumps(row)
        for address in extract_addresses(text):
            records.append(
                {
                    "source_type": "threat_feed",
                    "source_url": source_url,
                    "source_record_id": str(row.get("id") or address),
                    "indicator": address,
                    "original_timestamp": row.get("published") or row.get("timestamp"),
                    "extracted_context": text[:500],
                    "extraction_method": "csv_feed_regex",
                    "reliability": "feed_unverified",
                }
            )
    return records


def persist_evidence(db: Session, investigation_id: str, finding: dict[str, Any]) -> OsintEvidence | None:
    digest = hashlib.sha256(
        f"{investigation_id}|{finding.get('source_url')}|{finding.get('source_record_id')}|{finding.get('indicator')}".encode()
    ).hexdigest()
    existing = db.scalar(
        select(OsintEvidence).where(
            OsintEvidence.investigation_id == investigation_id,
            OsintEvidence.content_hash == digest,
        )
    )
    if existing:
        return None
    ts = None
    raw_ts = finding.get("original_timestamp")
    if raw_ts:
        try:
            ts = datetime.fromisoformat(str(raw_ts).replace("Z", "+00:00"))
        except ValueError:
            ts = None
    row = OsintEvidence(
        investigation_id=investigation_id,
        source_type=finding["source_type"],
        source_url=finding.get("source_url") or "",
        source_record_id=str(finding.get("source_record_id") or ""),
        indicator=(finding.get("indicator") or "").lower(),
        original_timestamp=ts,
        extracted_context=finding.get("extracted_context") or "",
        extraction_method=finding.get("extraction_method") or "unknown",
        verification_status="unverified",
        reliability=finding.get("reliability") or "unknown",
        content_hash=digest,
        extra={"notice": "Public text is untrusted. This is not a verified identity claim."},
    )
    db.add(row)
    db.flush()
    return row


def ingest_osint(db: Session, investigation: Investigation) -> dict[str, Any]:
    created = 0
    errors: list[str] = []
    if investigation.is_fixture:
        return {"created": 0, "errors": [], "notice": "Fixture investigation: live GitHub search skipped."}
    keywords = [investigation.title, investigation.seed_value, "ethereum"]
    try:
        for finding in search_github(keywords):
            if persist_evidence(db, investigation.id, finding):
                created += 1
        github_source = db.scalar(select(OsintSource).where(OsintSource.source_type == "github"))
        if github_source:
            github_source.status = "ok"
            github_source.last_success_at = datetime.now(UTC)
            github_source.last_error = None
    except Exception as exc:  # noqa: BLE001 - surface connector error to job
        errors.append(str(exc))
        github_source = db.scalar(select(OsintSource).where(OsintSource.source_type == "github"))
        if github_source:
            github_source.status = "error"
            github_source.last_error = str(exc)

    sources = db.scalars(select(OsintSource).where(OsintSource.enabled.is_(True))).all()
    for source in sources:
        if source.source_type == "github":
            continue
        try:
            body, ctype = fetch_public_url(source.endpoint)
            for finding in parse_feed(body, ctype, source.endpoint):
                if persist_evidence(db, investigation.id, finding):
                    created += 1
            source.status = "ok"
            source.last_success_at = datetime.now(UTC)
            source.last_error = None
        except FeedFetchError as exc:
            source.status = "error"
            source.last_error = str(exc)
            errors.append(f"{source.name}: {exc}")
        except Exception as exc:  # noqa: BLE001
            source.status = "error"
            source.last_error = str(exc)
            errors.append(f"{source.name}: {exc}")
    db.flush()
    return {"created": created, "errors": errors}
