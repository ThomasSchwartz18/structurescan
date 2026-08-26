import re
from pathlib import Path
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from confluence.api.app import STATIC_DIR, app

FORBIDDEN_WORDS = [
    r"\bbuy\b",
    r"\bsell\b",
    r"\blong\b",
    r"\bshort\b",
    r"\bentry\b",
    r"\bexit\b",
    r"\brecommend",
    r"\bsignal\b",
]

# Lines that legitimately contain the word as part of the app's own
# disclaimer/rule statement, not as user-facing trading-action language.
ALLOWLIST_SUBSTRINGS = [
    "not a recommendation",
]


@pytest.fixture
def client(tmp_path):
    state_file = tmp_path / "tickers.local.json"
    with patch("confluence.watchlist.STATE_FILE", state_file):
        yield TestClient(app)


def test_index_html_served_at_root(client):
    resp = client.get("/")
    assert resp.status_code == 200
    assert "text/html" in resp.headers["content-type"]
    assert "Confluence" in resp.text
    assert 'id="watchlist-table"' in resp.text


def test_styles_and_script_served(client):
    css_resp = client.get("/styles.css")
    assert css_resp.status_code == 200

    js_resp = client.get("/app.js")
    assert js_resp.status_code == 200


def test_api_routes_take_precedence_over_static_catch_all(client):
    resp = client.get("/api/meta")
    assert resp.status_code == 200
    assert resp.json()["data_source"] == "mock"


def test_mock_banner_element_present_and_hidden_by_default():
    html = (STATIC_DIR / "index.html").read_text(encoding="utf-8")
    assert 'id="mock-banner"' in html
    assert "hidden" in html


def test_static_assets_never_emit_trading_action_language():
    for filename in ["index.html", "styles.css", "app.js"]:
        text = (STATIC_DIR / filename).read_text(encoding="utf-8").lower()
        lines = text.splitlines()
        for pattern in FORBIDDEN_WORDS:
            for line in lines:
                if any(allowed in line for allowed in ALLOWLIST_SUBSTRINGS):
                    continue
                assert not re.search(pattern, line), (
                    f"{filename} contains forbidden phrase matching {pattern!r}: {line!r}"
                )
