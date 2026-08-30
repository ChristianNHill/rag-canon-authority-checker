"""Deliverable D: passage -> claims -> retrieve -> adjudicate -> resolve."""
from . import llm, resolve, retrieve


def run(tool, passage):
    policy = resolve.load_policy()
    chunks, matrix = retrieve.load_index()
    claims = llm.extract_claims(passage, tool)

    results = []
    for claim in claims:
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
        results.append({"claim": claim, **verdict})
    return results
