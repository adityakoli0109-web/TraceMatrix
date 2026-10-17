from __future__ import annotations

import argparse
import json
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path

from sqlalchemy import select

from app.config import get_settings
from app.db import SessionLocal, engine
from app.ethutil import normalize_address, to_checksum_address
from app.models import Base, GraphEdge, Investigation, InvestigationMember, OsintEvidence, OsintSource, User, Wallet
from app.security import hash_password
from app.services.ingest import persist_transaction
from app.services.osint import persist_evidence


def init_db() -> None:
    Base.metadata.create_all(bind=engine)


def bootstrap(email: str, password: str, name: str = "Administrator") -> None:
    if not password:
        raise SystemExit("BOOTSTRAP_ADMIN_PASSWORD is required")
    db = SessionLocal()
    try:
        existing = db.scalar(select(User).where(User.email == email.lower()))
        if existing:
            print(f"User {email} already exists")
            return
        user = User(email=email.lower(), password_hash=hash_password(password), full_name=name, role="admin")
        db.add(user)
        db.add(
            OsintSource(
                name="GitHub public search",
                source_type="github",
                endpoint="https://api.github.com",
                enabled=True,
                status="configured" if get_settings().github_token else "limited_unauthenticated",
            )
        )
        db.commit()
        print(f"Created admin {email}")
    finally:
        db.close()


def seed_demo(email: str) -> None:
    db = SessionLocal()
    try:
        user = db.scalar(select(User).where(User.email == email.lower()))
        if user is None:
            raise SystemExit("Bootstrap an admin before seeding demo data")
        fixture = json.loads((Path(__file__).resolve().parents[1] / "tests" / "fixtures" / "chain_sample.json").read_text())
        inv = Investigation(
            title="Demo fixture: sample neighborhood",
            description="Deterministic fixture dataset. Not live blockchain data.",
            seed_value=fixture["seed"],
            seed_type="address",
            objective="Demonstrate graph, OSINT overlap, and explainable scoring on known data.",
            status="completed",
            is_fixture=True,
            created_by=user.id,
            max_depth=2,
            max_transactions=50,
            selected_sources={"github": True, "chain": True, "threat_feeds": True},
        )
        db.add(inv)
        db.flush()
        db.add(InvestigationMember(investigation_id=inv.id, user_id=user.id, member_role="owner"))
        for address in fixture["wallets"]:
            if db.scalar(select(Wallet).where(Wallet.address == address)) is None:
                db.add(Wallet(address=address, checksum_address=to_checksum_address(address)))
        for tx in fixture["transactions"]:
            persist_transaction(db, tx, is_fixture=True)
            db.add(
                GraphEdge(
                    investigation_id=inv.id,
                    from_address=tx["from_address"],
                    to_address=tx["to_address"],
                    tx_hash=tx["tx_hash"],
                    token_address="native",
                    value_raw=Decimal(tx["value_wei"]),
                    timestamp=datetime.fromisoformat(tx["timestamp"].replace("Z", "+00:00")),
                )
            )
        for finding in fixture["osint"]:
            persist_evidence(db, inv.id, finding)
        db.commit()
        print(f"Seeded demo investigation {inv.id}")
    finally:
        db.close()


def main() -> None:
    parser = argparse.ArgumentParser(prog="tracematrix")
    sub = parser.add_subparsers(dest="cmd", required=True)
    sub.add_parser("init-db")
    boot = sub.add_parser("bootstrap")
    boot.add_argument("--email")
    boot.add_argument("--password")
    seed = sub.add_parser("seed-demo")
    seed.add_argument("--email")
    args = parser.parse_args()
    settings = get_settings()
    if args.cmd == "init-db":
        init_db()
        print("Schema created")
    elif args.cmd == "bootstrap":
        bootstrap(args.email or settings.bootstrap_admin_email, args.password or settings.bootstrap_admin_password)
    elif args.cmd == "seed-demo":
        seed_demo(args.email or settings.bootstrap_admin_email)


if __name__ == "__main__":
    main()
