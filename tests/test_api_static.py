import re
from pathlib import Path
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from confluence.api.app import STATIC_DIR, app

# Unambiguous recommendation/instruction verbs: never legitimate anywhere
# in the app, including the paper trading journal.
ALWAYS_FORBIDDEN = [
    r"\bbuy\b",
    r"\bsell\b",
    r"\brecommend",
]

# "long"/"short"/"entry"/"exit"/"signal" are NOT in the always-forbidden
# list: the paper trading journal legitimately needs them (trade
# direction, entry/exit price) to record decisions the *user* already
# made — that's categorically different from the screener issuing an
# instruction. They're still forbidden specifically from the screener's
# own descriptive-label vocabulary, checked separately below.
SCREENER_LABEL_FORBIDDEN = [
    r"\blong\b",
    r"\bshort\b",
    r"\bentry\b",
    r"\bexit\b",
    r"\bsignal\b",
] + ALWAYS_FORBIDDEN

SCREENER_LABEL_BLOCKS = ["STRUCTURE_LABELS", "ALIGNMENT_LABELS", "MA_STACK_LABELS"]

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


def test_static_assets_never_emit_unambiguous_recommendation_language():
    for filename in ["index.html", "styles.css", "app.js"]:
        text = (STATIC_DIR / filename).read_text(encoding="utf-8").lower()
        lines = text.splitlines()
        for pattern in ALWAYS_FORBIDDEN:
            for line in lines:
                if any(allowed in line for allowed in ALLOWLIST_SUBSTRINGS):
                    continue
                assert not re.search(pattern, line), (
                    f"{filename} contains forbidden phrase matching {pattern!r}: {line!r}"
                )


def test_screener_label_vocabulary_never_emits_trading_action_language():
    """The screener's own descriptive-state labels (structure/alignment/MA
    stack) must never drift into recommendation or position-direction
    language — unlike the paper trading journal, this is Confluence's own
    generated text, not the user's record of their own decision."""
    js_text = (STATIC_DIR / "app.js").read_text(encoding="utf-8")

    for block_name in SCREENER_LABEL_BLOCKS:
        match = re.search(rf"const {block_name}\s*=\s*\{{.*?\}};", js_text, re.DOTALL)
        assert match, f"could not find {block_name} block in app.js"
        block_text = match.group(0).lower()
        for pattern in SCREENER_LABEL_FORBIDDEN:
            assert not re.search(pattern, block_text), (
                f"{block_name} contains forbidden phrase matching {pattern!r}"
            )
