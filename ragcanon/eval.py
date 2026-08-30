"""Deliverable E: golden-set scorer.

Two scoring modes, not one: verdict + needs_review are checked by exact
match against a hand-derived expected value (deterministic, no judge,
free), while the winning citation is checked by an LLM judge for
plausibility rather than exact-match against one hand-picked quote --
real corpus evidence often has more than one chunk that would correctly
justify the same verdict, so there's no single "correct" citation string
to compare against.

`needs_review` is only exact-matched when a case sets an expected value.
For "conflicting" it's deterministic (always True) and always checked; for
other verdicts it depends on the model's own confidence score, which isn't
something independent inspection of the corpus can predict ahead of time,
so most cases leave it unset and unscored.

Reports per-stratum accuracy, not one aggregate number -- a single score
would hide whether the system is good at "clean" cases but bad at
"conflicting" ones, which is the interesting result.
"""
import json
from pathlib import Path

from . import check, llm, resolve, retrieve

ROOT = Path(__file__).resolve().parent.parent
GOLDEN_SET = ROOT / "golden_set.jsonl"


def load_golden_set():
    with open(GOLDEN_SET, encoding="utf-8") as f:
        return [json.loads(line) for line in f if line.strip()]


def score_case(case, chunks, matrix, policy):
    result = check.check_claim(case["tool"], case["claim"], chunks, matrix, policy)

    verdict_correct = result["verdict"] == case["expected_verdict"]

    needs_review_correct = None
    if case["expected_needs_review"] is not None:
        needs_review_correct = result["needs_review"] == case["expected_needs_review"]

    citation_plausible = None
    if result["winning_row"] is not None:
        w = result["winning_row"]
        citation_plausible = llm.judge_citation(case["claim"], w["relation"], w["quote"])

    return {
        "id": case["id"],
        "stratum": case["stratum"],
        "actual_verdict": result["verdict"],
        "expected_verdict": case["expected_verdict"],
        "verdict_correct": verdict_correct,
        "needs_review_correct": needs_review_correct,
        "citation_plausible": citation_plausible,
    }


def summarize(results):
    """Pure aggregation, no I/O -- per-stratum accuracy plus the two
    secondary rates, each only over cases that actually scored that axis."""
    by_stratum = {}
    for r in results:
        by_stratum.setdefault(r["stratum"], []).append(r)

    summary = {}
    for stratum, rows in by_stratum.items():
        nr_rows = [r for r in rows if r["needs_review_correct"] is not None]
        cite_rows = [r for r in rows if r["citation_plausible"] is not None]
        summary[stratum] = {
            "n": len(rows),
            "verdict_accuracy": sum(r["verdict_correct"] for r in rows) / len(rows),
            "needs_review_accuracy": (
                sum(r["needs_review_correct"] for r in nr_rows) / len(nr_rows)
                if nr_rows else None
            ),
            "citation_plausibility_rate": (
                sum(r["citation_plausible"] for r in cite_rows) / len(cite_rows)
                if cite_rows else None
            ),
        }
    return summary


def run():
    policy = resolve.load_policy()
    chunks, matrix = retrieve.load_index()
    cases = load_golden_set()
    results = [score_case(case, chunks, matrix, policy) for case in cases]
    return results, summarize(results)
