"""Deliverable B: local sentence-transformer embeddings -> embeddings.npy.

Runs entirely on-machine -- no API key, no rate limit, no cost. Switched
from Voyage after its no-payment-method throttle (3 RPM / 10K TPM) proved
unworkable in practice even with correct token-accurate batching and long
retry backoffs -- see DECISIONS.md for the full story. D-12 (cache by
content hash) and D-16 (normalized at write time, so retrieval is one
`matrix @ query`) carry over unchanged; D-13/D-14 (Voyage model, batching,
retries) no longer apply -- there's no rate limit or retry logic needed.
"""
import json
from pathlib import Path

import numpy as np
from sentence_transformers import SentenceTransformer

ROOT = Path(__file__).resolve().parent.parent
CHUNKS = ROOT / "chunks.jsonl"
EMBEDDINGS_OUT = ROOT / "embeddings.npy"
CACHE_OUT = ROOT / "embeddings_cache.jsonl"

MODEL = "BAAI/bge-small-en-v1.5"
# BGE's documented asymmetry: prefix the query only, embed documents as-is.
QUERY_PREFIX = "Represent this sentence for searching relevant passages: "
BATCH_SIZE = 64

_model = None


def _get_model():
    global _model
    if _model is None:
        _model = SentenceTransformer(MODEL)
    return _model


def load_chunks():
    with open(CHUNKS, encoding="utf-8") as f:
        return [json.loads(line) for line in f if line.strip()]


def _load_cache():
    cache = {}
    if CACHE_OUT.exists():
        with open(CACHE_OUT, encoding="utf-8") as f:
            for line in f:
                if line.strip():
                    row = json.loads(line)
                    cache[row["chunk_id"]] = row["embedding"]
    return cache


def embed_query(text):
    """Normalized query vector, ready for a dot product against the matrix."""
    vec = _get_model().encode(QUERY_PREFIX + text, normalize_embeddings=True)
    return np.asarray(vec, dtype=np.float32)


def run():
    chunks = load_chunks()
    cache = _load_cache()
    to_embed = [c for c in chunks if c["chunk_id"] not in cache]
    print(f"{len(chunks)} chunks, {len(to_embed)} new (cache hit for {len(chunks) - len(to_embed)})")

    if to_embed:
        model = _get_model()
        vectors = model.encode(
            [c["text"] for c in to_embed],
            batch_size=BATCH_SIZE,
            normalize_embeddings=True,
            show_progress_bar=True,
        )
        with open(CACHE_OUT, "a", encoding="utf-8") as cache_f:
            for c, v in zip(to_embed, vectors):
                cache[c["chunk_id"]] = v.tolist()
                cache_f.write(json.dumps({"chunk_id": c["chunk_id"], "embedding": v.tolist()}) + "\n")

    matrix = np.array([cache[c["chunk_id"]] for c in chunks], dtype=np.float32)
    np.save(EMBEDDINGS_OUT, matrix)
    print(f"{matrix.shape} -> {EMBEDDINGS_OUT}")
    return matrix
