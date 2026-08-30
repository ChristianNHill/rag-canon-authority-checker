"""Deliverable D: passage -> claims -> retrieve -> adjudicate -> resolve."""
from . import llm, resolve, retrieve


def check_claim(tool, claim, chunks, matrix, policy):
    """One claim -> resolved verdict. Split out of run() so deliverable E's
    eval harness can score a golden-set claim directly, without going
    through extract_claims() -- claim extraction isn't part of what E's
    scorer is testing."""
    rows = []
    for r in retrieve.retrieve(claim, chunks, matrix):
        adj = llm.adjudicate(claim, r["text"])
        rows.append({
            "relation": adj.relation,
            "confidence": adj.confidence,
            "quote": adj.quote,
            "tool": r["tool"],
            "tier": r["tier"],
            "date_or_version": r["date_or_version"],
            "superseded_by": r["superseded_by"],
            "source": r["source"],
        })
    verdict = resolve.resolve(tool, rows, policy["confidence_threshold"])
    return {"claim": claim, **verdict}


def run(tool, passage):
    policy = resolve.load_policy()
    chunks, matrix = retrieve.load_index()
    claims = llm.extract_claims(passage, tool)
    return [check_claim(tool, claim, chunks, matrix, policy) for claim in claims]
