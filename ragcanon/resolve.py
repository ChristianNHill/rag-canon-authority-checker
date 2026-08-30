"""Deliverable D: policy layer -- pure resolver, no I/O.

Four verdict states, not three: confirmed / contradicted / conflicting /
not_established. not_established is kept separate from confirmed/contradicted
because "no evidence found" is a corpus-coverage gap, not an adjudication
result. conflicting is kept separate from contradicted because "the
top-authority sources disagree with each other" is a docs problem (the canon
itself is unsettled), not a passage-author problem -- collapsing it into
contradicted would route it to the wrong queue.

Authority ordering ("which row wins") is supersession-first: a chunk with
superseded_by set always loses to a non-superseded chunk, regardless of tier
or date, because the source itself disclaims it. Among non-superseded rows,
recency (date_or_version) only decides when BOTH competing rows carry a real
date -- otherwise tier decides. This follows from the corpus, not a
preference: only changelog entries (and Claude Code's dated digest pages)
carry a real date. An undated tier-1 doc has no timestamp to be out-dated
by, so treating "recency" as decisive there would just be comparing
meaningless acquisition dates.

Cross-tool mismatch is not a verdict state (see PLAN.md) -- a chunk from a
different tool than the claim's target tool can still correctly
support/contradict/be-irrelevant-to the claim. It's a flag on the winning
row instead, surfaced alongside the verdict.
"""
from functools import cmp_to_key
from pathlib import Path
from typing import List, Literal, Optional, TypedDict

import yaml

ROOT = Path(__file__).resolve().parent.parent
POLICY_FILE = ROOT / "canon_policy.yaml"

CONFIDENCE_THRESHOLD_DEFAULT = 0.7


class EvidenceRow(TypedDict):
    relation: Literal["supports", "contradicts", "irrelevant"]
    confidence: float
    quote: str
    tool: str
    tier: int
    date_or_version: Optional[str]
    superseded_by: Optional[str]
    source: str


class Verdict(TypedDict):
    verdict: Literal["confirmed", "contradicted", "conflicting", "not_established"]
    needs_review: bool
    winning_row: Optional[EvidenceRow]
    cross_tool_mismatch: Optional[bool]
    winners: List[EvidenceRow]


def load_policy():
    with open(POLICY_FILE, encoding="utf-8") as f:
        return yaml.safe_load(f)


def _compare(a: EvidenceRow, b: EvidenceRow) -> int:
    """-1 if a outranks b, 1 if b outranks a, 0 if tied on authority."""
    a_superseded = a["superseded_by"] is not None
    b_superseded = b["superseded_by"] is not None
    if a_superseded != b_superseded:
        return -1 if not a_superseded else 1

    both_dated = a["date_or_version"] is not None and b["date_or_version"] is not None
    if both_dated and a["date_or_version"] != b["date_or_version"]:
        return -1 if a["date_or_version"] > b["date_or_version"] else 1

    if a["tier"] != b["tier"]:
        return -1 if a["tier"] < b["tier"] else 1
    return 0


def resolve(target_tool: str, rows: List[EvidenceRow],
            confidence_threshold: float = CONFIDENCE_THRESHOLD_DEFAULT) -> Verdict:
    candidates = [r for r in rows if r["relation"] != "irrelevant"]
    if not candidates:
        return {"verdict": "not_established", "needs_review": False,
                "winning_row": None, "cross_tool_mismatch": None, "winners": []}

    non_superseded = [r for r in candidates if r["superseded_by"] is None]
    pool = non_superseded or candidates  # only reachable if every row is superseded

    ordered = sorted(pool, key=cmp_to_key(_compare))
    best = ordered[0]
    winners = [r for r in ordered if _compare(r, best) == 0]

    relations = {r["relation"] for r in winners}
    if len(relations) > 1:
        verdict = "conflicting"
    elif relations == {"supports"}:
        verdict = "confirmed"
    else:
        verdict = "contradicted"

    winning_row = max(winners, key=lambda r: r["confidence"])
    needs_review = verdict == "conflicting" or winning_row["confidence"] < confidence_threshold

    return {
        "verdict": verdict,
        "needs_review": needs_review,
        "winning_row": winning_row,
        "cross_tool_mismatch": winning_row["tool"] != target_tool,
        "winners": winners,
    }
