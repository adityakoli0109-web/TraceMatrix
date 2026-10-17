from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.ethutil import normalize_address, to_checksum_address
from app.models import (
    ChainTransaction,
    GraphEdge,
    Investigation,
    InvestigationWallet,
    TokenTransfer,
    Wallet,
)
from app.services.blockchain import lookup


def _upsert_wallet(db: Session, address: str, seen: datetime | None) -> Wallet:
    norm = normalize_address(address)
    wallet = db.scalar(select(Wallet).where(Wallet.address == norm))
    if wallet is None:
        wallet = Wallet(address=norm, checksum_address=to_checksum_address(norm), first_seen=seen, last_seen=seen)
        db.add(wallet)
        db.flush()
        return wallet
    if seen:
        if wallet.first_seen is None or seen < wallet.first_seen:
            wallet.first_seen = seen
        if wallet.last_seen is None or seen > wallet.last_seen:
            wallet.last_seen = seen
    return wallet


def _link_wallet(db: Session, investigation_id: str, wallet: Wallet, hop: int) -> None:
    existing = db.scalar(
        select(InvestigationWallet).where(
            InvestigationWallet.investigation_id == investigation_id,
            InvestigationWallet.wallet_id == wallet.id,
        )
    )
    if existing:
        existing.hop_distance = min(existing.hop_distance, hop)
        return
    db.add(InvestigationWallet(investigation_id=investigation_id, wallet_id=wallet.id, hop_distance=hop))


def persist_transaction(db: Session, tx: dict, is_fixture: bool = False) -> ChainTransaction:
    existing = db.scalar(select(ChainTransaction).where(ChainTransaction.tx_hash == tx["tx_hash"].lower()))
    ts = None
    if tx.get("timestamp"):
        ts = datetime.fromisoformat(tx["timestamp"].replace("Z", "+00:00"))
        if ts.tzinfo is None:
            ts = ts.replace(tzinfo=UTC)
    if existing:
        return existing
    row = ChainTransaction(
        tx_hash=tx["tx_hash"].lower(),
        block_number=tx.get("block_number"),
        timestamp=ts,
        from_address=(tx.get("from_address") or "").lower(),
        to_address=(tx.get("to_address") or None),
        value_wei=Decimal(str(tx.get("value_wei") or 0)),
        status=tx.get("status"),
        gas_used=tx.get("gas_used"),
        gas_price_wei=Decimal(str(tx["gas_price_wei"])) if tx.get("gas_price_wei") else None,
        input_data=tx.get("input_data"),
        is_fixture=is_fixture or bool(tx.get("is_fixture")),
    )
    db.add(row)
    db.flush()
    return row


def persist_transfer(db: Session, transfer: dict, is_fixture: bool = False) -> None:
    exists = db.scalar(
        select(TokenTransfer).where(
            TokenTransfer.tx_hash == transfer["tx_hash"].lower(),
            TokenTransfer.log_index == int(transfer.get("log_index") or 0),
        )
    )
    if exists:
        return
    ts = None
    if transfer.get("timestamp"):
        ts = datetime.fromisoformat(transfer["timestamp"].replace("Z", "+00:00"))
    db.add(
        TokenTransfer(
            tx_hash=transfer["tx_hash"].lower(),
            log_index=int(transfer.get("log_index") or 0),
            token_address=transfer["token_address"].lower(),
            from_address=transfer["from_address"].lower(),
            to_address=transfer["to_address"].lower(),
            value_raw=Decimal(str(transfer.get("value_raw") or 0)),
            decimals=int(transfer.get("decimals") or 18),
            symbol=transfer.get("symbol"),
            timestamp=ts,
            is_fixture=is_fixture,
        )
    )


def ingest_for_investigation(db: Session, investigation: Investigation, cancel_check=None) -> dict:
    seed = investigation.seed_value
    result = lookup(seed)
    is_fixture = bool(result.get("is_fixture") or investigation.is_fixture)
    txs: list[dict] = []
    transfers: list[dict] = []
    if result["kind"] == "transaction":
        txs = [result["transaction"]]
        transfers = result.get("token_transfers") or []
    else:
        txs = result.get("transactions") or []
        if result.get("limitation") and not txs:
            return {
                "ingested_transactions": 0,
                "ingested_transfers": 0,
                "limitation": result["limitation"],
                "provider": result.get("provider"),
                "notice": result.get("notice"),
            }

    limit = min(investigation.max_transactions, 500)
    hop = 0
    ingested_tx = 0
    ingested_tf = 0
    for tx in txs[:limit]:
        if cancel_check and cancel_check():
            break
        row = persist_transaction(db, tx, is_fixture=is_fixture)
        ingested_tx += 1
        ts = row.timestamp
        from_w = _upsert_wallet(db, row.from_address, ts)
        _link_wallet(db, investigation.id, from_w, hop)
        if row.to_address:
            to_w = _upsert_wallet(db, row.to_address, ts)
            _link_wallet(db, investigation.id, to_w, hop + 1 if row.from_address == seed.lower() else hop)
            edge_exists = db.scalar(
                select(GraphEdge).where(
                    GraphEdge.investigation_id == investigation.id,
                    GraphEdge.tx_hash == row.tx_hash,
                    GraphEdge.from_address == row.from_address,
                    GraphEdge.to_address == row.to_address,
                    GraphEdge.token_address == "native",
                )
            )
            if not edge_exists and row.to_address:
                db.add(
                    GraphEdge(
                        investigation_id=investigation.id,
                        from_address=row.from_address,
                        to_address=row.to_address,
                        tx_hash=row.tx_hash,
                        token_address="native",
                        value_raw=row.value_wei,
                        timestamp=row.timestamp,
                    )
                )
    for transfer in transfers:
        persist_transfer(db, transfer, is_fixture=is_fixture)
        ingested_tf += 1
        if transfer.get("from_address") and transfer.get("to_address"):
            db.add(
                GraphEdge(
                    investigation_id=investigation.id,
                    from_address=transfer["from_address"].lower(),
                    to_address=transfer["to_address"].lower(),
                    tx_hash=transfer["tx_hash"].lower(),
                    token_address=transfer["token_address"].lower(),
                    value_raw=Decimal(str(transfer.get("value_raw") or 0)),
                    timestamp=None,
                )
            )
            _link_wallet(db, investigation.id, _upsert_wallet(db, transfer["from_address"], None), hop)
            _link_wallet(db, investigation.id, _upsert_wallet(db, transfer["to_address"], None), hop)

    if is_fixture:
        investigation.is_fixture = True
        from app.services.blockchain import load_fixture_bundle
        from app.services.osint import persist_evidence

        for finding in load_fixture_bundle().get("osint", []):
            persist_evidence(db, investigation.id, finding)
    db.flush()
    return {
        "ingested_transactions": ingested_tx,
        "ingested_transfers": ingested_tf,
        "limitation": result.get("limitation"),
        "provider": result.get("provider"),
        "notice": result.get("notice"),
        "is_fixture": is_fixture,
    }
