from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import httpx

from app.config import get_settings
from app.ethutil import is_address, is_tx_hash, normalize_address, parse_hex_int, raw_to_decimal_string, to_checksum_address

TRANSFER_TOPIC = "0xddf252ad1be2c89b69c2b068fc378daa952ba7f163c4a11628f55a4df523b3ef"
FIXTURE_PATH = Path(__file__).resolve().parents[2] / "tests" / "fixtures" / "chain_sample.json"


class ProviderError(Exception):
    pass


class ProviderNotConfigured(Exception):
    pass


def integration_status() -> dict[str, Any]:
    settings = get_settings()
    rpc = "configured" if settings.eth_rpc_url else "not_configured"
    explorer = "configured" if settings.etherscan_api_key else "not_configured"
    fixture = "enabled" if settings.allow_fixture_provider else "disabled"
    limitations = []
    if not settings.etherscan_api_key:
        limitations.append(
            "JSON-RPC nodes do not index historical address activity. Configure an Etherscan-compatible API for address history."
        )
    if not settings.eth_rpc_url and not settings.allow_fixture_provider:
        limitations.append("No Ethereum JSON-RPC URL is configured.")
    return {
        "rpc": rpc,
        "explorer": explorer,
        "fixture_provider": fixture,
        "limitations": limitations,
    }


def _rpc(method: str, params: list[Any]) -> Any:
    settings = get_settings()
    if not settings.eth_rpc_url:
        raise ProviderNotConfigured("ETH_RPC_URL is not configured")
    payload = {"jsonrpc": "2.0", "id": 1, "method": method, "params": params}
    try:
        with httpx.Client(timeout=20.0) as client:
            response = client.post(settings.eth_rpc_url, json=payload)
            response.raise_for_status()
            body = response.json()
    except httpx.HTTPError as exc:
        raise ProviderError(f"RPC request failed: {exc}") from exc
    if "error" in body:
        raise ProviderError(str(body["error"]))
    return body.get("result")


def lookup(query: str) -> dict[str, Any]:
    settings = get_settings()
    if settings.allow_fixture_provider:
        fixture = _fixture_lookup(query)
        if fixture:
            return fixture
    if is_tx_hash(query):
        return _lookup_tx(query)
    if is_address(query):
        return _lookup_address(query)
    raise ValueError("Provide an Ethereum address or transaction hash")


def _lookup_tx(tx_hash: str) -> dict[str, Any]:
    tx = _rpc("eth_getTransactionByHash", [tx_hash])
    if not tx:
        raise ProviderError("Transaction not found")
    receipt = _rpc("eth_getTransactionReceipt", [tx_hash]) or {}
    block = None
    ts = None
    if tx.get("blockNumber"):
        block = _rpc("eth_getBlockByNumber", [tx["blockNumber"], False])
        if block and block.get("timestamp"):
            ts = datetime.fromtimestamp(parse_hex_int(block["timestamp"]), tz=UTC)
    value_wei = parse_hex_int(tx.get("value"))
    transfers = _transfers_from_receipt(receipt, ts)
    return {
        "kind": "transaction",
        "is_fixture": False,
        "transaction": _normalize_tx(tx, receipt, ts, value_wei),
        "token_transfers": transfers,
        "provider": "json-rpc",
    }


def _lookup_address(address: str) -> dict[str, Any]:
    settings = get_settings()
    checksum = to_checksum_address(address)
    norm = normalize_address(address)
    balance = None
    if settings.eth_rpc_url:
        try:
            raw = _rpc("eth_getBalance", [checksum, "latest"])
            balance = {
                "wei": str(parse_hex_int(raw)),
                "eth": raw_to_decimal_string(parse_hex_int(raw), 18),
            }
        except ProviderError:
            balance = None
    history: list[dict[str, Any]] = []
    limitation = None
    provider = "json-rpc"
    if settings.etherscan_api_key:
        history = _etherscan_txlist(norm)
        provider = "etherscan-compatible"
    else:
        limitation = (
            "Address history requires an Etherscan-compatible explorer API. "
            "A standard JSON-RPC node cannot list historical transactions for an address."
        )
    return {
        "kind": "address",
        "is_fixture": False,
        "address": checksum,
        "normalized": norm,
        "balance": balance,
        "transactions": history,
        "limitation": limitation,
        "provider": provider,
    }


def _normalize_tx(tx: dict, receipt: dict, ts: datetime | None, value_wei: int) -> dict[str, Any]:
    to_addr = tx.get("to")
    return {
        "tx_hash": tx.get("hash"),
        "block_number": parse_hex_int(tx.get("blockNumber")) if tx.get("blockNumber") else None,
        "timestamp": ts.isoformat() if ts else None,
        "from_address": (tx.get("from") or "").lower(),
        "to_address": to_addr.lower() if to_addr else None,
        "value_wei": str(value_wei),
        "value_eth": raw_to_decimal_string(value_wei, 18),
        "status": "success" if receipt.get("status") in {"0x1", "0x01", 1} else receipt.get("status"),
        "gas_used": parse_hex_int(receipt.get("gasUsed")) if receipt.get("gasUsed") else parse_hex_int(tx.get("gas")),
        "gas_price_wei": str(parse_hex_int(tx.get("gasPrice"))),
        "input_data": tx.get("input"),
    }


def _topic_address(topic: str) -> str:
    return ("0x" + topic[-40:]).lower()


def _transfers_from_receipt(receipt: dict, ts: datetime | None) -> list[dict[str, Any]]:
    transfers = []
    for log in receipt.get("logs") or []:
        topics = log.get("topics") or []
        if not topics or topics[0].lower() != TRANSFER_TOPIC:
            continue
        if len(topics) < 3:
            continue
        raw = parse_hex_int(log.get("data"))
        transfers.append(
            {
                "tx_hash": log.get("transactionHash"),
                "log_index": parse_hex_int(log.get("logIndex")),
                "token_address": (log.get("address") or "").lower(),
                "from_address": _topic_address(topics[1]),
                "to_address": _topic_address(topics[2]),
                "value_raw": str(raw),
                "value_formatted": raw_to_decimal_string(raw, 18),
                "decimals": 18,
                "symbol": None,
                "timestamp": ts.isoformat() if ts else None,
            }
        )
    return transfers


def _etherscan_txlist(address: str) -> list[dict[str, Any]]:
    settings = get_settings()
    params = {
        "module": "account",
        "action": "txlist",
        "address": address,
        "startblock": 0,
        "endblock": 99999999,
        "page": 1,
        "offset": min(settings.max_ingest_transactions, 100),
        "sort": "desc",
        "apikey": settings.etherscan_api_key,
    }
    try:
        with httpx.Client(timeout=20.0) as client:
            response = client.get(settings.etherscan_api_url, params=params)
            response.raise_for_status()
            body = response.json()
    except httpx.HTTPError as exc:
        raise ProviderError(f"Explorer request failed: {exc}") from exc
    if str(body.get("status")) == "0" and body.get("message") not in {"No transactions found"}:
        raise ProviderError(body.get("result") or body.get("message") or "Explorer error")
    items = body.get("result") or []
    out = []
    if isinstance(items, str):
        return out
    for item in items:
        value_wei = int(item.get("value") or 0)
        ts = datetime.fromtimestamp(int(item["timeStamp"]), tz=UTC) if item.get("timeStamp") else None
        out.append(
            {
                "tx_hash": item.get("hash"),
                "block_number": int(item["blockNumber"]) if item.get("blockNumber") else None,
                "timestamp": ts.isoformat() if ts else None,
                "from_address": (item.get("from") or "").lower(),
                "to_address": (item.get("to") or "").lower() or None,
                "value_wei": str(value_wei),
                "value_eth": raw_to_decimal_string(value_wei, 18),
                "status": "success" if str(item.get("txreceipt_status", "1")) == "1" else "failed",
                "gas_used": int(item["gasUsed"]) if item.get("gasUsed") else None,
                "gas_price_wei": str(int(item["gasPrice"])) if item.get("gasPrice") else None,
                "is_fixture": False,
            }
        )
    return out


def load_fixture_bundle() -> dict[str, Any]:
    return json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))


def _fixture_lookup(query: str) -> dict[str, Any] | None:
    if not FIXTURE_PATH.exists():
        return None
    data = load_fixture_bundle()
    q = query.lower()
    for tx in data["transactions"]:
        if tx["tx_hash"].lower() == q:
            return {
                "kind": "transaction",
                "is_fixture": True,
                "transaction": tx,
                "token_transfers": [t for t in data["token_transfers"] if t["tx_hash"] == tx["tx_hash"]],
                "provider": "fixture",
                "notice": "Fixture result — not live blockchain data.",
            }
    for wallet in data["wallets"]:
        if wallet.lower() == q:
            txs = [
                t
                for t in data["transactions"]
                if t["from_address"] == q or (t.get("to_address") or "") == q
            ]
            return {
                "kind": "address",
                "is_fixture": True,
                "address": wallet,
                "normalized": q,
                "balance": None,
                "transactions": txs,
                "limitation": None,
                "provider": "fixture",
                "notice": "Fixture result — not live blockchain data.",
            }
    return None
