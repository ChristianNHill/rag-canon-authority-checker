"""Deliverable C: claim extraction + per-(claim, chunk) adjudication.

D-02 (both calls live here -- same shape: a Claude call with a Pydantic
output schema). D-20 (claude-opus-5 for both, to start). D-21 (adaptive
thinking, high effort -- adjudication is the intelligence-sensitive step).
D-22 (adjudicate one chunk at a time, not all k at once -- source
separation is the entire point). D-23 (the returned quote must verify as a
real substring of the chunk; retried if not). D-24 (prompt caching on the
adjudication system prompt, which is identical across every call). D-25
(Pydantic output via `messages.parse`). D-37 (a response cache keyed by
request content, so replaying is free -- lands here, not in eval, so
nothing built against it during C/D gets thrown away later).

D-26 (3 retries, then mark the claim "error") is a per-claim orchestration
decision that belongs to deliverable D's `check.py`, not here: these
functions raise after exhausting retries -- both for real API failures and
for a quote that never verifies -- and the caller decides what "error"
means for its own row schema.
"""
import hashlib
import json
import os
from pathlib import Path
from typing import List, Literal

import anthropic
from pydantic import BaseModel

ROOT = Path(__file__).resolve().parent.parent
CACHE_OUT = ROOT / "llm_cache.jsonl"

MODEL = "claude-opus-5"
MAX_RETRIES = 3


class ExtractedClaims(BaseModel):
    claims: List[str]


class Adjudication(BaseModel):
    relation: Literal["supports", "contradicts", "irrelevant"]
    quote: str
    confidence: float


_ADJUDICATE_SYSTEM = """You adjudicate whether one piece of evidence supports, \
contradicts, or is irrelevant to one claim about an AI coding agent tool \
(Claude Code, Cursor, or Codex).

Judge using only what the evidence explicitly says, not prior knowledge.

- "supports": the evidence confirms the claim.
- "contradicts": the evidence states something that makes the claim false \
-- whether that's a different behavior, a different default, or a feature \
that has since been renamed, deprecated, or removed.
- "irrelevant": the evidence doesn't bear on the claim at all.

`quote` must be an exact, verbatim substring of the evidence text below -- \
something that could be highlighted in the source. Never paraphrase or \
summarize it. `confidence` is your confidence in the relation judgment, \
from 0.0 to 1.0."""


def _client():
    if "ANTHROPIC_API_KEY" not in os.environ:
        env_file = ROOT / ".env"
        if env_file.exists():
            for line in env_file.read_text().splitlines():
                if line.startswith("ANTHROPIC_API_KEY="):
                    os.environ["ANTHROPIC_API_KEY"] = line.split("=", 1)[1].strip()
    return anthropic.Anthropic()


_cache = None


def _load_cache():
    global _cache
    if _cache is None:
        _cache = {}
        if CACHE_OUT.exists():
            with open(CACHE_OUT, encoding="utf-8") as f:
                for line in f:
                    if line.strip():
                        row = json.loads(line)
                        _cache[row["key"]] = row["response"]
    return _cache


def _cache_key(system, messages, schema_name, salt=0):
    blob = json.dumps(
        {"model": MODEL, "system": system, "messages": messages, "schema": schema_name, "salt": salt},
        sort_keys=True,
    )
    return hashlib.sha256(blob.encode()).hexdigest()[:24]


def _parse_cached(client, system, messages, output_format, salt=0):
    cache = _load_cache()
    key = _cache_key(system, messages, output_format.__name__, salt)
    if key in cache:
        return output_format.model_validate(cache[key])

    last_error = None
    for attempt in range(MAX_RETRIES):
        try:
            response = client.messages.parse(
                model=MODEL,
                max_tokens=4096,
                system=system,
                messages=messages,
                thinking={"type": "adaptive"},
                output_config={"effort": "high"},
                output_format=output_format,
            )
            parsed = response.parsed_output
            cache[key] = parsed.model_dump()
            with open(CACHE_OUT, "a", encoding="utf-8") as f:
                f.write(json.dumps({"key": key, "response": cache[key]}) + "\n")
            return parsed
        except Exception as e:
            last_error = e
    raise last_error


def extract_claims(passage, tool):
    """Factual, checkable claims about `tool`'s behavior found in `passage`."""
    system = [{
        "type": "text",
        "text": (
            f"Extract factual, checkable claims about {tool}'s behavior, "
            "features, or configuration from the passage below. Each claim "
            "is a single, self-contained statement that could be true or "
            "false on its own -- skip opinions, questions, and vague "
            "statements that don't assert anything checkable."
        ),
    }]
    messages = [{"role": "user", "content": passage}]
    return _parse_cached(_client(), system, messages, ExtractedClaims).claims


def adjudicate(claim, chunk_text):
    """One (claim, chunk) pair -> relation + verbatim quote + confidence.

    Raises if the quote never verifies as a real substring of `chunk_text`
    after MAX_RETRIES attempts (D-23) -- same as any other exhausted-retry
    failure; the caller (deliverable D) decides how to record that.
    """
    system = [{
        "type": "text",
        "text": _ADJUDICATE_SYSTEM,
        "cache_control": {"type": "ephemeral"},  # D-24: identical on every call
    }]
    messages = [{"role": "user", "content": f"Claim: {claim}\n\nEvidence:\n{chunk_text}"}]

    client = _client()
    last_bad_quote = None
    for attempt in range(MAX_RETRIES):
        result = _parse_cached(client, system, messages, Adjudication, salt=attempt)
        if result.quote in chunk_text:
            return result
        last_bad_quote = result.quote
    raise ValueError(f"quote did not verify after {MAX_RETRIES} attempts: {last_bad_quote!r}")
