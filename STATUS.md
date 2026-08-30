# Status

Where this project actually stands, kept current across sessions. See
`PLAN.md` for the corpus/schema design and `DECISIONS.md` for the full
decision log with reasoning — this file is just "what's done, what's next."

## Immediate next step

**Deliverable C has never actually been verified end-to-end.** `llm.py` is
written (claim extraction + adjudication, both tested in isolation only via
skipped-without-a-key smoke tests), but every real run against it failed —
first on Voyage-unrelated auth issues, then on a "identity-linked API key
needs `anthropic-workspace-id`" error. A new workspace-scoped key is now in
`.env`, **but `python -m ragcanon check claude_code samples/passage.md` has
not been re-run since**. `llm_cache.jsonl` doesn't exist on disk, which is
the tell — no adjudication call has ever succeeded.

Run that command first. If it works, confirm C's actual acceptance
criteria: claims come out at a sensible granularity, and every returned
quote verifies as a real substring of its chunk (already enforced in code
via retry-then-raise, but not yet observed on a real passage).

## Done

- **A — Corpus data layer.** `acquire.py` + `ingest.py`. 597 documents,
  10,003 chunks across claude_code (201 docs / 6,338 chunks), cursor
  (162 / 2,357), codex (234 / 1,308). Section-bounded chunking, code-fence
  and table-row aware, content-hash chunk IDs, heading-path + char-span
  locators. `pytest tests/test_ingest.py` — real tests, all passing.
- **B — Retrieval layer.** `embed.py` + `retrieve.py`. Local
  `sentence-transformers` (`BAAI/bge-small-en-v1.5`, 384-dim) after Voyage's
  no-payment-method throttle proved unworkable — see DECISIONS.md's B
  section for the full story. Cosine top-8-per-tool, then merged (not a
  flat top-k — handles the Claude-Code-is-10x-bigger imbalance). Cache-hit
  re-embedding confirmed working. `pytest tests/test_retrieve.py` — real
  tests, no API calls, all passing.
- **C — Reasoning layer, code only.** `llm.py`. `extract_claims()` and
  `adjudicate()`, both via `claude-opus-5` + `messages.parse` structured
  output, adaptive thinking, high effort, prompt caching on the
  adjudication system prompt, a response cache (`llm_cache.jsonl`, not yet
  populated -- see above), quote-verification with retry. Written and unit
  logic reviewed, **not yet run successfully against the real API.**

## Not started

- **D — Policy layer.** `canon_policy.yaml` + `resolve()` (pure function,
  no I/O). This is where the real product decisions land:
  - How many verdict states, and why "not established" is or isn't its own
    state.
  - The exact recency-vs-tier override rule (a recent changelog can
    outrank older official docs; settled that this is a second axis, not
    settled what the actual rule is).
  - The confidence threshold a flag has to clear to reach a human review
    queue.
  - `check.py` (passage → claims → retrieve → adjudicate → resolve) also
    belongs here — right now `cli.py`'s `check` subcommand does everything
    except the resolve step, printing raw adjudications with no verdict.
- **E — Evaluation layer.** Golden set (planted + real cases, stratified:
  hard contradiction / soft contradiction / cross-tool / not-established /
  clean), stratified scorer, scoring modes (not yet chosen).
- **F — Shot list.** Not started; low priority relative to D/E.
- **G — Human loop.** Review queue, adjudication states
  (confirmed / not-a-conflict / intentional departure / unclear), feedback
  into golden set + policy suggestions + a decisions ledger ingested at
  tier 0. Not started.

## Known deferred items (not blocking, just not done)

- Tiers 4 (blog posts) and 5 (community content) are defined in the schema
  but have zero chunks — see DECISIONS.md's A section for why.
- Cursor's changelog only has its ~5 most-recently-server-rendered entries.
  Full history needs interactive browser automation against a client-side
  infinite scroll with no bulk export — explicitly deferred, ruled "ship
  with recent-only, revisit if eval shows a gap."
- `superseded_by` is regex-detected, explicit-only, best-effort (~18 hits
  across the whole corpus, not hand-verified beyond spot checks).
- `date_or_version` is null for most doc pages (vendor-date proxy) except
  Claude Code's dated weekly digest pages and changelog entries.

## Environment

- Repo: `~/Code/rag-canon-authority-checker`, pushed to
  `https://github.com/ChristianNHill/rag-canon-authority-checker` (public).
- `.env` (gitignored) needs `ANTHROPIC_API_KEY` — a **workspace-scoped**
  key, not an identity-linked/account-wide one (the latter needs an
  `anthropic-workspace-id` header this code doesn't send). No other keys
  needed — Voyage was dropped entirely in favor of local embeddings.
- `data/`, `manifest.jsonl`, `chunks.jsonl`, `embeddings.npy`,
  `embeddings_cache.jsonl`, `llm_cache.jsonl` are all gitignored and
  regenerable: `python -m ragcanon acquire && ... ingest && ... embed`
  rebuilds everything from scratch (acquire takes a few minutes; embed
  takes under a minute once cached, ~35s cold).
- `pytest tests/` — 7 real tests always run; 2 LLM smoke tests skip
  automatically without a configured key.
