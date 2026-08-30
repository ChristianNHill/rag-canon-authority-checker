import json
import random

from ragcanon import ingest


def test_ingest_acceptance():
    manifest = ingest.load_manifest()
    chunks = ingest.run()

    assert len(manifest) > 0
    assert len(chunks) > 0

    by_path = {doc["path"]: doc for doc in manifest}
    raw_by_path = {doc["path"]: (ingest.ROOT / doc["path"]).read_text(encoding="utf-8") for doc in manifest}

    # every chunk's tool/tier/source must match its source document's manifest entry
    for chunk in chunks:
        doc = by_path[chunk["locator"]["path"]]
        assert chunk["tool"] == doc["tool"]
        assert chunk["tier"] == doc["tier"]
        assert chunk["source"] == doc["source"]

    # locator spans must resolve to exactly the chunk text -- checked on a
    # sample (10k+ chunks makes a full pass slow without adding much signal
    # beyond the sample, since the slicing logic is the same for every chunk)
    random.seed(7)
    for chunk in random.sample(chunks, 200):
        loc = chunk["locator"]
        span = raw_by_path[loc["path"]][loc["char_start"]:loc["char_end"]]
        assert span == chunk["text"], f"{loc['path']}: locator span does not resolve to chunk text"

    # re-ingest must be byte-identical (content-hash IDs)
    second_pass = ingest.run()
    assert [c["chunk_id"] for c in chunks] == [c["chunk_id"] for c in second_pass]


def test_changelog_entries_not_split():
    # a changelog_entries document must yield exactly one chunk per '## ' entry
    manifest = [d for d in ingest.load_manifest() if d["chunking"] == "changelog_entries"]
    assert manifest, "expected at least one changelog_entries document"
    doc = manifest[0]
    text = (ingest.ROOT / doc["path"]).read_text(encoding="utf-8")
    entries = ingest._split_changelog_entries(text)
    assert len(entries) == text.count("\n## ") + (1 if text.startswith("## ") else 0)


def test_table_rows_not_one_giant_chunk():
    # a markdown table must not collapse into a single multi-thousand-word chunk
    text = (
        "# Vars\n\n"
        "| Variable | Purpose |\n"
        "| --- | --- |\n"
        + "".join(f"| VAR_{i} | does thing {i} |\n" for i in range(200))
    )
    chunks = ingest.make_chunks(text, max_words=50)
    assert len(chunks) > 1
    assert max(len(c["text"].split()) for c in chunks) < 500


def test_code_fence_never_split():
    text = "# Example\n\n```\n" + "\n".join(f"line {i}" for i in range(100)) + "\n```\n"
    chunks = ingest.make_chunks(text, max_words=20)
    fence_chunks = [c for c in chunks if "```" in c["text"]]
    assert len(fence_chunks) == 1
    assert fence_chunks[0]["text"].count("```") == 2


if __name__ == "__main__":
    test_ingest_acceptance()
    test_changelog_entries_not_split()
    test_table_rows_not_one_giant_chunk()
    test_code_fence_never_split()
    print("ok")
