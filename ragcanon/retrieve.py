"""Deliverable B: cosine top-k retrieval.

D-15/D-18 (top_k per claim), D-17 (tier-blind -- and, for this corpus,
tool-blind: no filtering to a "target tool" upstream, since that would make
a cross-tool-confusion finding unreachable, same reasoning as tier-blindness
in the original design). D-19 (no score floor, always return k and let the
LLM say "irrelevant").

Retrieval is top_k **per tool, then merged** rather than one flat top_k over
the whole matrix -- Claude Code's official corpus runs roughly an order of
magnitude larger than Cursor's or Codex's, and a flat top_k would let that
size difference alone crowd out the smaller tools' evidence. Per-tool top_k
guarantees each tool gets a fair look regardless of corpus size.
"""
import numpy as np

from . import embed

TOP_K_PER_TOOL = 8


def load_index():
    chunks = embed.load_chunks()
    matrix = np.load(embed.EMBEDDINGS_OUT)
    return chunks, matrix


def rank(chunks, scores, top_k_per_tool=TOP_K_PER_TOOL):
    """Pure ranking: top_k_per_tool highest-scoring chunks per tool, merged.
    No API calls -- takes precomputed scores so this is fully unit-testable."""
    by_tool = {}
    for chunk, score in zip(chunks, scores):
        by_tool.setdefault(chunk["tool"], []).append((float(score), chunk))

    results = []
    for scored in by_tool.values():
        scored.sort(key=lambda pair: -pair[0])
        for score, chunk in scored[:top_k_per_tool]:
            results.append({**chunk, "score": score})
    results.sort(key=lambda c: -c["score"])
    return results


def retrieve(query, chunks, matrix, top_k_per_tool=TOP_K_PER_TOOL):
    q = embed.embed_query(query)
    scores = matrix @ q  # cosine similarity: both sides are L2-normalized
    return rank(chunks, scores, top_k_per_tool)
