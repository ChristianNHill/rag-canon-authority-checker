import os

import pytest

from ragcanon import llm

_HAS_KEY = bool(os.environ.get("ANTHROPIC_API_KEY")) or (
    (llm.ROOT / ".env").exists()
    and any(
        line.startswith("ANTHROPIC_API_KEY=") and line.strip() != "ANTHROPIC_API_KEY="
        for line in (llm.ROOT / ".env").read_text().splitlines()
    )
)

pytestmark = pytest.mark.skipif(not _HAS_KEY, reason="no ANTHROPIC_API_KEY configured")


def test_extract_claims_smoke():
    passage = "Claude Code supports MCP servers, which extend it with external tools."
    claims = llm.extract_claims(passage, "Claude Code")
    assert isinstance(claims, list)
    assert len(claims) > 0
    assert all(isinstance(c, str) and c.strip() for c in claims)


def test_adjudicate_quote_verifies():
    chunk = "MCP servers let Claude Code connect to external tools and data sources."
    result = llm.adjudicate("Claude Code supports MCP servers", chunk)
    assert result.relation in ("supports", "contradicts", "irrelevant")
    assert result.quote in chunk  # D-23: the quote must be a real substring
    assert 0.0 <= result.confidence <= 1.0


if __name__ == "__main__":
    if _HAS_KEY:
        test_extract_claims_smoke()
        test_adjudicate_quote_verifies()
        print("ok")
    else:
        print("skipped: no ANTHROPIC_API_KEY configured")
