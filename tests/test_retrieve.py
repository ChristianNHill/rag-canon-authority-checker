from ragcanon import retrieve


def _chunk(tool, tier, score_hint):
    return {"tool": tool, "tier": tier, "chunk_id": f"{tool}-{tier}-{score_hint}"}


def test_per_tool_top_k_not_global_top_k():
    # 20 claude_code chunks all outscoring every cursor/codex chunk -- a flat
    # top_k over everything would starve the smaller tools entirely. Per-tool
    # top_k must still return codex/cursor chunks despite being outscored.
    chunks = [_chunk("claude_code", 1, i) for i in range(20)]
    chunks += [_chunk("cursor", 1, i) for i in range(3)]
    chunks += [_chunk("codex", 1, i) for i in range(3)]
    scores = [0.9] * 20 + [0.1] * 3 + [0.1] * 3

    results = retrieve.rank(chunks, scores, top_k_per_tool=2)

    tools_present = {r["tool"] for r in results}
    assert tools_present == {"claude_code", "cursor", "codex"}
    assert sum(1 for r in results if r["tool"] == "claude_code") == 2
    assert sum(1 for r in results if r["tool"] == "cursor") == 2
    assert sum(1 for r in results if r["tool"] == "codex") == 2


def test_tier_blind_within_a_tool():
    # a lower-tier chunk that scores higher must still beat a higher-tier
    # chunk that scores lower -- ranking is on score alone, tier plays no
    # part in retrieval (tier only matters later, in the resolver).
    chunks = [_chunk("claude_code", tier=1, score_hint="official"),
              _chunk("claude_code", tier=3, score_hint="cookbook")]
    scores = [0.2, 0.9]

    results = retrieve.rank(chunks, scores, top_k_per_tool=1)

    assert len(results) == 1
    assert results[0]["tier"] == 3  # the higher-scoring one wins despite lower tier


def test_results_sorted_by_score_descending():
    chunks = [_chunk("claude_code", 1, "a"), _chunk("cursor", 1, "b"), _chunk("codex", 1, "c")]
    scores = [0.3, 0.9, 0.6]

    results = retrieve.rank(chunks, scores, top_k_per_tool=1)

    assert [r["score"] for r in results] == sorted((r["score"] for r in results), reverse=True)


if __name__ == "__main__":
    test_per_tool_top_k_not_global_top_k()
    test_tier_blind_within_a_tool()
    test_results_sorted_by_score_descending()
    print("ok")
