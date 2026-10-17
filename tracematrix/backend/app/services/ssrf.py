from __future__ import annotations

import ipaddress
import socket
from urllib.parse import urlparse

import httpx

from app.config import get_settings


class FeedFetchError(Exception):
    pass


def _is_blocked_ip(ip: str) -> bool:
    parsed = ipaddress.ip_address(ip)
    return bool(
        parsed.is_private
        or parsed.is_loopback
        or parsed.is_link_local
        or parsed.is_reserved
        or parsed.is_multicast
        or parsed.is_unspecified
    )


def validate_feed_url(url: str) -> str:
    settings = get_settings()
    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"}:
        raise FeedFetchError("Only http/https feed URLs are allowed")
    host = (parsed.hostname or "").lower()
    if not host:
        raise FeedFetchError("Feed URL is missing a host")
    if settings.feed_allowlist and host not in settings.feed_allowlist:
        raise FeedFetchError("Feed host is not on the allowlist")
    if not settings.feed_allowlist:
        raise FeedFetchError("OSINT_FEED_ALLOWLIST is empty; remote feeds are blocked until configured")
    try:
        infos = socket.getaddrinfo(host, parsed.port or (443 if parsed.scheme == "https" else 80))
    except OSError as exc:
        raise FeedFetchError(f"Unable to resolve feed host: {exc}") from exc
    for info in infos:
        ip = info[4][0]
        if _is_blocked_ip(ip):
            raise FeedFetchError("Feed host resolves to a blocked address")
    return url


def fetch_public_url(url: str, *, timeout: float = 15.0, max_bytes: int = 1_000_000) -> tuple[str, str]:
    validate_feed_url(url)
    try:
        with httpx.Client(timeout=timeout, follow_redirects=False) as client:
            response = client.get(url, headers={"User-Agent": "TraceMatrix/1.0 (public-osint)"})
            response.raise_for_status()
            content = response.content[: max_bytes + 1]
            if len(content) > max_bytes:
                raise FeedFetchError("Feed exceeded maximum response size")
            ctype = response.headers.get("content-type", "application/octet-stream")
            return content.decode("utf-8", errors="replace"), ctype
    except httpx.HTTPError as exc:
        raise FeedFetchError(f"Feed request failed: {exc}") from exc
