from __future__ import annotations

import re
ADDRESS_RE = re.compile(r"^0x[0-9a-fA-F]{40}$")
TX_HASH_RE = re.compile(r"^0x[0-9a-fA-F]{64}$")
ADDRESS_IN_TEXT_RE = re.compile(r"0x[0-9a-fA-F]{40}")


def is_address(value: str) -> bool:
    return bool(ADDRESS_RE.match(value or ""))


def is_tx_hash(value: str) -> bool:
    return bool(TX_HASH_RE.match(value or ""))


def classify_seed(value: str) -> str:
    if is_address(value):
        return "address"
    if is_tx_hash(value):
        return "tx_hash"
    raise ValueError("Seed must be a 0x-prefixed Ethereum address or 32-byte transaction hash")


def normalize_address(value: str) -> str:
    if not is_address(value):
        raise ValueError("Invalid Ethereum address")
    return value.lower()


def keccak_256(data: bytes) -> bytes:
    # stdlib sha3_256 is Keccak in hashlib.sha3? On Python, sha3_256 is NIST SHA3, not Keccak.
    # EIP-55 requires Keccak-256. Use a pure-python Keccak if pycryptodome isn't a dep.
    return _keccak(data)


def _keccak(data: bytes) -> bytes:
    from app.keccak import keccak_256 as _k

    return _k(data)


def to_checksum_address(address: str) -> str:
    addr = normalize_address(address)[2:]
    hashed = keccak_256(addr.encode("ascii")).hex()
    out = "0x"
    for char, h in zip(addr, hashed[: len(addr)], strict=True):
        out += char.upper() if int(h, 16) >= 8 else char
    return out


def is_checksum_valid(address: str) -> bool:
    if not is_address(address):
        return False
    if address[2:] == address[2:].lower() or address[2:] == address[2:].upper():
        return True
    return address == to_checksum_address(address)


def parse_hex_int(value: str | int | None) -> int:
    if value is None or value == "":
        return 0
    if isinstance(value, int):
        return value
    return int(value, 16)


def raw_to_decimal_string(raw: int, decimals: int = 18) -> str:
    """Exact integer-to-decimal conversion. Never uses floating point."""
    negative = raw < 0
    raw = abs(int(raw))
    if decimals <= 0:
        text = str(raw)
        return f"-{text}" if negative else text
    padded = str(raw).zfill(decimals + 1)
    whole, frac = padded[:-decimals], padded[-decimals:]
    frac = frac.rstrip("0")
    text = f"{int(whole)}.{frac}" if frac else str(int(whole))
    return f"-{text}" if negative else text


def extract_addresses(text: str) -> list[str]:
    found = {normalize_address(m) for m in ADDRESS_IN_TEXT_RE.findall(text or "")}
    return sorted(found)
