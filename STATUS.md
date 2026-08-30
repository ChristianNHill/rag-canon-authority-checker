# Status

Where this project actually stands, kept current across sessions. See
`PLAN.md` for the corpus/schema design and `DECISIONS.md` for the full
decision log with reasoning — this file is just "what's done, what's next."

## Immediate next step

**G — Human loop** is next: a real review queue (somewhere to write
adjudications, not just a design for one), the four adjudication states,
and feedback into the golden set + policy suggestions + a decisions ledger
ingested at tier 0. See `README.md`'s "Human in the loop" section for the
intended shape.

Also worth doing before G, or alongside it: the golden set is thin (9 cases,
1 each for conflicting/cross_tool/soft_contradiction), and E's first real
run already found a real miss worth investigating further — see D's entry
below. `check.py`'s output is a bare `List[dict]` printed by `cli.py` — no
structured export format, no batch-passage mode yet. Low priority unless a
later deliverable needs one.

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

- **E — Evaluation layer.** `golden_set.jsonl` (13 cases across 6 strata:
  hard_contradiction ×3, conflicting ×2, cross_tool ×1, soft_contradiction ×1,
  not_established ×3, clean ×3 — `conflicting` added as its own stratum
  beyond the original 5 in `PLAN.md`, since it's one of `resolve()`'s 4
  verdict states and real evidence for it was already in hand) + `eval.py`
  (`score_case()` runs the real pipeline per case, `summarize()` is pure/
  unit-tested, no I/O). Two scoring modes: verdict + needs_review by exact
  match against a value hand-derived from reading the actual corpus text
  (never by running the system and copying its own output — that would be
  circular), and the winning citation by an LLM judge (`llm.judge_citation()`)
  for plausibility rather than exact-match, since real evidence often has
  more than one chunk that would correctly justify the same verdict.
  `pytest tests/test_eval.py` — 3 unit tests, all passing.

  First real run 2026-08-30 (9 cases): 7/9 verdicts correct. Both misses are
  real findings, not harness bugs — full writeup in `README.md`'s "Where it
  fails": (1) `hard-02` got the right verdict (contradicted) but the judge
  correctly flagged the winning citation as a weak link (about Sonnet 4.6
  and usage credits, not squarely about Sonnet-4.5-on-Max); (2) my own
  `not_established-01` case turned out to be a bad label, not a system
  failure — Claude Code has a real `/batch` skill that does something
  adjacent to the claim, the system found it at 0.55 confidence and
  correctly routed it to review (below the 0.7 threshold) rather than
  asserting it outright.

  Second run 2026-08-30 (13 cases, after adding a 3rd hard_contradiction, a
  2nd conflicting, and a 3rd each of not_established/clean, all mined from
  the real corpus the same way as the first batch): 11/13 correct. All 4 new
  cases landed clean; the only 2 misses are the same 2 from the first run
  (good reproducibility signal). cross_tool and soft_contradiction are still
  1 case each — hardest strata to find organically, see `README.md`'s
  Evaluation section for why.

## Not started

- **F — Shot list.** Not started; low priority relative to G.
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
- `pytest tests/` — 20 real tests always run; 2 LLM smoke tests skip
  automatically without a configured key.
