# Status

Where this project actually stands, kept current across sessions. See
`PLAN.md` for the corpus/schema design and `DECISIONS.md` for the full
decision log with reasoning — this file is just "what's done, what's next."

## Immediate next step

**E — Evaluation layer** is next: a golden set (planted + real cases,
stratified hard-contradiction / soft-contradiction / cross-tool /
not-established / clean) and a stratified scorer against `resolve()`'s four
verdict states. This is also the first real chance to check whether the
`confidence_threshold: 0.7` in `canon_policy.yaml` is actually the right
number, or just a placeholder that happened to work on one sample passage.

`check.py`'s output is a bare `List[dict]` printed by `cli.py` — no
structured export format, no batch-passage mode yet. Low priority unless E's
scorer needs one.

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
- **C — Reasoning layer.** `llm.py`. `extract_claims()` and `adjudicate()`,
  both via `claude-opus-5` + `messages.parse` structured output, adaptive
  thinking, high effort, prompt caching on the adjudication system prompt, a
  response cache (`llm_cache.jsonl`), quote-verification with retry.
  Verified end-to-end against the real API 2026-08-30 (a workspace-scoped
  key was needed — an identity-linked one fails without an
  `anthropic-workspace-id` header): 4 claims extracted from
  `samples/passage.md` at sensible granularity, every returned quote
  confirmed as a real substring of its chunk. `pytest tests/` — 9/9
  including the 2 LLM smoke tests that previously auto-skipped without a
  key.
- **D — Policy layer.** `canon_policy.yaml` (one knob:
  `confidence_threshold: 0.7`, a provisional round number pending E's golden
  set) + `ragcanon/resolve.py` (`resolve()`, pure, no I/O) + `ragcanon/check.py`
  (the passage → claims → retrieve → adjudicate → resolve orchestration;
  `cli.py`'s `check` subcommand calls this instead of printing raw
  adjudications). Four verdict states — `confirmed` / `contradicted` /
  `conflicting` / `not_established` — kept separate because "no evidence"
  and "sources disagree with each other" are different problems from "the
  claim is wrong," and route to different follow-up. Authority ordering:
  supersession absolute override, then recency only when both competing rows
  have a real (non-proxy) date, else tier — this follows from the corpus
  (only changelog entries and Claude Code's dated digest pages have real
  dates, so recency can't decide most tier-1-vs-tier-2 comparisons). Cross-
  tool mismatch is a flag on the winning row, not a 5th state (matches
  `PLAN.md`'s original resolution). Review routing: `conflicting` always
  reviewed; `confirmed`/`contradicted` reviewed only if the winning row's
  confidence is below the threshold. `pytest tests/test_resolve.py` — 10
  unit tests, all passing. Verified against the real API on
  `samples/passage.md` 2026-08-30: all four states fired in one run,
  including a genuine `conflicting` catch (two Claude Code docs disagree on
  whether MCP servers connect automatically) and a cross-tool tag that
  correctly didn't flip the verdict since the winning row was same-tool.

## Not started

- **E — Evaluation layer.** Golden set (planted + real cases, stratified:
  hard contradiction / soft contradiction / cross-tool / not-established /
  clean), stratified scorer, scoring modes (not yet chosen).
- **F — Shot list.** Not started; low priority relative to E/G.
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
- `pytest tests/` — 17 real tests always run; 2 LLM smoke tests skip
  automatically without a configured key.
