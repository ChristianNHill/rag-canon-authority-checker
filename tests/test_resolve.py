from ragcanon import resolve


def _row(relation, confidence=0.9, tier=1, date_or_version=None,
         superseded_by=None, tool="claude_code", quote="q", source="s"):
    return {
        "relation": relation, "confidence": confidence, "quote": quote,
        "tool": tool, "tier": tier, "date_or_version": date_or_version,
        "superseded_by": superseded_by, "source": source,
    }


def test_no_evidence_is_not_established():
    v = resolve.resolve("claude_code", [_row("irrelevant")])
    assert v["verdict"] == "not_established"
    assert not v["needs_review"]
    assert v["winning_row"] is None


def test_single_support_is_confirmed():
    v = resolve.resolve("claude_code", [_row("supports")])
    assert v["verdict"] == "confirmed"
    assert not v["needs_review"]


def test_single_contradiction_is_contradicted():
    v = resolve.resolve("claude_code", [_row("contradicts")])
    assert v["verdict"] == "contradicted"


def test_higher_tier_wins_over_lower_tier():
    # tier 1 (official) contradicts, tier 3 (cookbook) supports -- tier 1 wins
    rows = [_row("contradicts", tier=1), _row("supports", tier=3)]
    v = resolve.resolve("claude_code", rows)
    assert v["verdict"] == "contradicted"


def test_same_tier_disagreement_is_conflicting():
    rows = [_row("supports", tier=1, tool="claude_code"),
            _row("contradicts", tier=1, tool="cursor")]
    v = resolve.resolve("claude_code", rows)
    assert v["verdict"] == "conflicting"
    assert v["needs_review"]
    assert len(v["winners"]) == 2


def test_recency_only_decides_when_both_dated():
    # newer changelog entry (tier 2, dated) contradicts; older changelog
    # entry (tier 2, dated) supports -- same tier, so recency must decide.
    rows = [_row("supports", tier=2, date_or_version="2025-01-01"),
            _row("contradicts", tier=2, date_or_version="2026-01-01")]
    v = resolve.resolve("claude_code", rows)
    assert v["verdict"] == "contradicted"
    assert v["winning_row"]["date_or_version"] == "2026-01-01"


def test_recency_does_not_cross_tiers_when_only_one_side_dated():
    # an undated tier-1 doc has no real timestamp -- a dated tier-2 entry
    # must NOT out-rank it on "recency" since the comparison isn't apples
    # to apples. Tier decides instead.
    rows = [_row("contradicts", tier=1, date_or_version=None),
            _row("supports", tier=2, date_or_version="2026-01-01")]
    v = resolve.resolve("claude_code", rows)
    assert v["verdict"] == "contradicted"


def test_superseded_always_loses_regardless_of_tier():
    rows = [_row("supports", tier=1, superseded_by="new-doc"),
            _row("contradicts", tier=3)]
    v = resolve.resolve("claude_code", rows)
    assert v["verdict"] == "contradicted"


def test_low_confidence_winner_flags_review():
    v = resolve.resolve("claude_code", [_row("supports", confidence=0.4)])
    assert v["verdict"] == "confirmed"
    assert v["needs_review"]


def test_cross_tool_mismatch_flagged_on_winning_row():
    v = resolve.resolve("claude_code", [_row("contradicts", tool="cursor")])
    assert v["cross_tool_mismatch"] is True


if __name__ == "__main__":
    test_no_evidence_is_not_established()
    test_single_support_is_confirmed()
    test_single_contradiction_is_contradicted()
    test_higher_tier_wins_over_lower_tier()
    test_same_tier_disagreement_is_conflicting()
    test_recency_only_decides_when_both_dated()
    test_recency_does_not_cross_tiers_when_only_one_side_dated()
    test_superseded_always_loses_regardless_of_tier()
    test_low_confidence_winner_flags_review()
    test_cross_tool_mismatch_flagged_on_winning_row()
    print("ok")
