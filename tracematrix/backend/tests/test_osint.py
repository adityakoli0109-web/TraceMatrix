from app.services.osint import parse_feed
from app.services.reports import _csv_safe
from app.services.ssrf import FeedFetchError, validate_feed_url
from app.config import get_settings


def test_parse_json_and_csv_feeds():
    json_body = '[{"id":"1","address":"0x3333333333333333333333333333333333333333"}]'
    recs = parse_feed(json_body, "application/json", "https://feeds.example/test.json")
    assert recs[0]["indicator"] == "0x3333333333333333333333333333333333333333"
    csv_body = "id,wallet\n9,0x1111111111111111111111111111111111111111\n"
    recs = parse_feed(csv_body, "text/csv", "https://feeds.example/test.csv")
    assert recs[0]["indicator"].startswith("0x1111")


def test_csv_formula_escape():
    assert _csv_safe("=CMD()") == "'=CMD()"
    assert _csv_safe("normal") == "normal"


def test_feed_allowlist_blocks_by_default():
    try:
        validate_feed_url("https://evil.example/feed.json")
        assert False, "should have blocked"
    except FeedFetchError:
        pass
    get_settings.cache_clear()
