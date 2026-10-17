from app.ethutil import (
    classify_seed,
    extract_addresses,
    is_address,
    is_checksum_valid,
    is_tx_hash,
    raw_to_decimal_string,
    to_checksum_address,
)


def test_address_and_hash_validation():
    assert is_address("0x1111111111111111111111111111111111111111")
    assert not is_address("1111111111111111111111111111111111111111")
    assert is_tx_hash("0x" + "ab" * 32)
    assert not is_tx_hash("0xabc")
    assert classify_seed("0x1111111111111111111111111111111111111111") == "address"
    assert classify_seed("0x" + "aa" * 32) == "tx_hash"


def test_exact_token_conversion():
    assert raw_to_decimal_string(0, 18) == "0"
    assert raw_to_decimal_string(1, 18) == "0.000000000000000001"
    assert raw_to_decimal_string(10**18, 18) == "1"
    assert raw_to_decimal_string(15 * 10**17, 18) == "1.5"
    assert raw_to_decimal_string(12345, 6) == "0.012345"
    assert raw_to_decimal_string(-10**18, 18) == "-1"


def test_keccak_empty():
    from app.keccak import keccak_256

    assert keccak_256(b"").hex() == "c5d2460186f7233c927e7db2dcc703c0e500b653ca82273b7bfad8045d85a470"


def test_checksum_and_extraction():
    addr = "0x5aAeb6053F3E94C9b9A09f33669435E7Ef1BeAed"
    assert is_checksum_valid(addr)
    assert to_checksum_address(addr.lower()) == addr
    found = extract_addresses(f"see {addr} and noise")
    assert found == [addr.lower()]
