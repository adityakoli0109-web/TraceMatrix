import httpx
import pytest

from app.services.blockchain import ProviderError, _rpc


def test_rpc_error_is_not_fabricated(monkeypatch):
    class Boom:
        def __init__(self, *args, **kwargs):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def post(self, *args, **kwargs):
            raise httpx.ConnectError("nope")

    monkeypatch.setattr("app.services.blockchain.httpx.Client", Boom)
    monkeypatch.setattr("app.services.blockchain.get_settings", lambda: type("S", (), {"eth_rpc_url": "http://127.0.0.1:9"})())
    with pytest.raises(ProviderError):
        _rpc("eth_blockNumber", [])
