# Decisions

Ruled, with the options considered and why. Grouped by deliverable.

**Pivot note:** the corpus changed from an Arthurian-legend stand-in to real
documentation for three AI coding agents (Claude Code, Cursor, Codex) — see
`PLAN.md` for the context. D-01, D-03, D-04, D-05 (naming, layout, Python
version, dependency management) carried over unchanged. Everything about the
corpus itself (D-06 through D-11 below) was re-decided for the new domain;
the original Arthurian-era rulings are kept in the appendix for provenance,
not because they're still in effect.

## A — Corpus data layer

**D-01 — Name.** `rag-canon-authority-checker`, package `ragcanon`. Chosen
over the more generic `canon-consistency-checker` to name what the system
actually does: retrieval over a canon, resolved by source authority. Still
apt after the pivot — "canon" now means "the current state of a tool's
documentation" rather than Arthurian legend, but the mechanism is identical.

**D-03 — Layout.** Flat modules under `ragcanon/`, no `src/` layer.

**D-04 — Python version.** 3.14.5, no pin needed (verified for `anthropic`,
`voyageai`, `numpy`, `pydantic`).

**D-05 — Dependency management.** `pyproject.toml` + `pip install -e .`.
`pyyaml` was dropped once the pivot removed the only file that used it
(the old hand-authored `sources.yaml`) — acquisition now generates its own
manifest, so nothing in the pipeline parses YAML any more.

**D-06 — Two-phase data layer: acquire, then ingest.** The Arthurian corpus
was four texts, hand-vendored once. This corpus is ~600 documents fetched
from three different sites, re-fetchable and meant to be re-run as docs
change — that's mechanical, repeatable work, so it became its own module
(`acquire.py`) instead of a one-time manual step. `acquire.py` fetches and
filters, writing raw files under `data/<tool>/...` plus one `manifest.jsonl`
row per document (`path, tool, tier, source, date_or_version, chunking`).
`ingest.py` reads the manifest and chunks each file — the manifest plays the
per-document metadata role `sources.yaml` used to play, just generated
instead of hand-authored, since nobody can hand-enumerate 600 pages.

**D-06a — Per-tool acquisition sources actually used** (see `PLAN.md` for the
original survey this executes):

| Tool | Official docs (tier 1) | Changelog (tier 2) | Cookbook (tier 3) |
|---|---|---|---|
| `claude_code` | `code.claude.com/docs/llms-full.txt`, split into 191 pages on the `# Title` + `Source: <url>` marker pattern | `CHANGELOG.md` from `anthropics/claude-code`, 380 `## <version>` entries | READMEs from the 9 `anthropics/*` repos listed in `PLAN.md` |
| `cursor` | `.md` twins of every in-scope URL from `cursor.com/llms.txt` (160 of 161 fetched; 1 failed) | recent entries only — see D-06c | `github.com/cursor/plugins` README |
| `codex` | `learn.chatgpt.com/docs/codex-manual.md` split by `### Title` / `Source:` sections, filtered to 89 of 179 (see D-06b) | GitHub Releases API for `openai/codex`, non-prerelease tags only (142 found) | `README.md`, `AGENTS.md`, `SECURITY.md` from `github.com/openai/codex` |

**D-06b — Codex's shared-hub filtering, as actually implemented.** The
`codex-manual.md` file's own per-section titles are too sparse to classify
against (no one-line description, unlike the llms.txt index). So scope
filtering runs against `learn.chatgpt.com/llms.txt` instead — which does
carry a description per page — matching on `"codex" in (title + description
text).lower()`, then intersecting that URL set with the manual's sections.
Five sibling pages of clearly-in-scope categories were added by hand after a
manual spot-check because their one-line description didn't happen to say
"Codex" even though the page obviously is (`Speed`, `Sample Configuration`,
`Local environments`, `Permission Modes`, `Building an AI-Native Engineering
Team`) — see `_CODEX_INCLUDE_OVERRIDES` in `acquire.py`. This is the
"page-by-page against titles/paths, spot-check the boundary" approach from
`PLAN.md`, not a full-content classification pass.

**D-06c — Cursor's full changelog history was not acquired.** The plan's
working assumption was "paginated HTML, ingest all of it." Investigation
found something worse: `cursor.com/changelog` is a client-side infinite
scroll with no bulk export, no per-entry permalinks in the sitemap, and no
discoverable pagination API (`?page=N`, `/api/changelog`, etc. all just
return the same SPA shell). The static page server-renders only its ~5 most
recent entries — that's what got vendored (`changelog-recent.md`). Getting
the rest means either driving a real browser through repeated "load more"
clicks, or reverse-engineering whatever internal call the button makes by
inspecting live network traffic — a materially different (and slower, more
fragile, more request-heavy against a third-party site) undertaking than
the "scrape some paginated HTML" the original decision assumed. Flagged back rather than either silently under-delivering against "all of
it" or silently spending a lot of interactive-automation effort on a
marketing site. **Ruled: ship with recent-only.** Revisit only if the golden
set (deliverable E) shows a real gap from missing changelog depth.

**D-07 — Chunk unit: section-bounded, not paragraph-bounded.** A chunk never
crosses an H2/H3 boundary (forces a flush), and within a section, blocks
(paragraphs, table rows, code fences) are grouped up to a ~250-word soft
cap — same "never split an atomic block" rule as the Arthurian project, but
the definition of "atomic block" now includes two more cases discovered
while building this: a **code fence** (opening to closing `` ``` ``, however
long) and **a markdown table row** (a whole table with no blank lines
between rows would otherwise be one indivisible multi-thousand-word block —
rows are split individually, header+separator kept together as the first
row's context). H1 (page title) and H4+ headings update the citation's
heading path but don't force a chunk flush; only H2/H3 do.

*Known ceiling, not fixed:* a long bullet/numbered list with no blank lines
between items is still one atomic block like a table would have been —
observed pushing a single changelog chunk to ~3.6K words. Same fix as the
table case (split by list item) if this turns out to matter for retrieval or
adjudication quality; marked with a `ponytail:` comment in `ingest.py` rather
than fixed pre-emptively.

**D-08 — No boilerplate stripping needed.** Unlike the Gutenberg texts, every
acquired document is already a clean, single-purpose doc/changelog/README
file — there's no license-page or navigation-chrome layer to strip.

**D-09 — Locator format.** `path` (the vendored file) + `heading_path` (e.g.
`Flags > --dangerously-skip-permissions`) + char span. The span is sliced
directly from the file (`text[char_start:char_end]`), not reconstructed by
joining block text — joining introduced a real bug during the Arthurian
build (reconstructed text didn't match the source when paragraphs had
irregular gaps) and the fix was to always slice, never rejoin; same
discipline applied here from the start.

**D-10 — Chunk ID stability.** `sha256(tool + path + text)[:16]` — content
only, no offsets, same reasoning as before.

**D-11 — Storage format.** `manifest.jsonl` (documents) + `chunks.jsonl`
(chunks), both greppable JSONL. `embeddings.npy` arrives in B.

**Schema fields not covered above** (see `PLAN.md` for the reasoning):
`tier` and `source` are copied straight from the manifest row onto every
chunk from that document. `date_or_version` is `null` for most doc pages
(vendor-date proxy, per plan) except Claude Code's dated `whats-new/YYYY-wWW`
pages and every changelog entry (Codex: the release's `published_at`; Claude
Code: none extracted — the version number itself *is* the entry's identity,
extracting a date would need a second GitHub API round-trip per entry for
marginal benefit). `superseded_by` is populated by a regex over each chunk's
own text — `deprecated`/`removed` near `in favor of X` / `replaced by X` /
`. Use X instead` — flattening whitespace first so a hard-wrapped markdown
link doesn't break the match. Explicit-only, as decided: 18 chunks matched
across the whole corpus, output not hand-verified beyond a handful of spot
checks (including the intended real example, Codex's
`codex mcp-server` → `Codex app server`) — some captures truncate early on
an incidental decimal point (e.g. "Sonnet 4.6" reads as a sentence boundary).
Accepted as a best-effort layer per the original scoping, not a guarantee.

## B — Retrieval layer

**D-12 — Embedding cache.** `embeddings_cache.jsonl` keyed by `chunk_id`
(already a content hash, so no separate cache key needed). Re-running
`embed` only pays for chunks whose ID isn't already cached — same content,
same ID, same vector, free.

**D-13 — Model + input-type asymmetry.** `voyage-4`, `input_type="document"`
for corpus chunks and `input_type="query"` for a submitted query, as the
plan called for.

**D-14 — Batching, in practice.** The plan's "batch 128, 3 retries" needed
revision against a real constraint: Voyage throttles accounts without a
payment method to **3 RPM / 10K TPM** (confirmed live — the 200M free
tokens still apply either way, a payment method only removes the throttle).
Fixed batch sizes don't respect a token cap, so batches are now built
greedily under a **9000-token budget per batch**, and paced at ~21s between
requests. First attempt at the token budget used a word-count estimate
(`words × 1.3`) — that undercounted badly on code-heavy docs (symbols,
identifiers, URLs tokenize far less efficiently than prose) and caused
batches to blow past the real cap regardless of pacing. Fixed by using
Voyage's own bundled tokenizer (`client.tokenize()` / `count_tokens()`) for
exact counts instead — it runs locally, no API call, no rate limit of its
own. Real corpus total: 2,004,168 tokens (matches the plan's ~2M estimate),
max single chunk 2,748 tokens.

A second real failure mode showed up even with correct batch sizes: the
RPM bucket resets on a **calendar minute**, not a rolling window, so a
retry after ~21s can still land inside the same already-exhausted minute.
Retry-on-rate-limit now waits a full 65s (past any bucket boundary) rather
than the ~21s used for pacing between already-succeeding batches.

**D-15/D-18 revised — top_k is per tool, not global.** The plan's `top_k=8`
assumed one corpus; this one has three tools of very different size
(Claude Code's official docs run roughly an order of magnitude larger than
Cursor's or Codex's). A flat top_k over the whole matrix would let that size
difference alone crowd out the smaller tools' evidence — exactly the
corpus-imbalance risk flagged as deferred to B in `PLAN.md`. Resolved:
retrieve top 8 **per tool**, then merge and re-sort by score. This also
happens to be free — since `tool` is already a mandatory field on every
chunk, per-tool grouping needs no new retrieval-time judgment call.

**D-16 — Metric.** Cosine via one `matrix @ query`, both sides L2-normalized
at write/query time, unchanged from the plan.

**D-17 — Tier-blind retrieval, extended to tool-blind.** Ranking uses score
alone; tier plays no part (`tests/test_retrieve.py::test_tier_blind_within_a_tool`
is a real, deterministic test for this, not a spot check). This corpus adds
the same argument one level up: retrieval must not filter to a "target
tool" either, or a cross-tool-confusion finding (guidance for Cursor
misapplied to Claude Code) would be unreachable, mirroring D-17's original
reasoning exactly.

**D-19 — No score floor**, carried over unchanged.

**D-13/D-14 revised — dropped Voyage, switched to local embeddings.**
Even with token-accurate batching (above) and a 65-second wait on every
retry, the no-payment-method throttle kept rejecting the very first request
of every fresh run — stricter or longer-window than the "3 RPM" the error
message stated, and not something worth continuing to guess at blindly
after three real failed attempts. Switched to `sentence-transformers`
(`BAAI/bge-small-en-v1.5`, 384-dim, runs locally via `torch`) — no API key,
no rate limit, no cost, and full-corpus embedding dropped from an
~80-minute throttled slog to ~7-8 minutes of local CPU inference. This
was flagged as reopenable in the original plan ("say the word and I'll
re-open the embeddings question") for exactly this situation.
Consequences: the "two keys, no other services" story becomes **one key**
(Anthropic, needed starting at deliverable C) rather than two; the
`.env` scaffold from B was removed since nothing reads it anymore.
BGE's documented query/passage asymmetry (prefix the query only) is used
in place of Voyage's `input_type` parameter — same idea, different
mechanism, same "free accuracy" reasoning from D-13.
`retrieve.py`'s cosine-matrix logic is completely unchanged by this swap.

## C — Reasoning layer

**D-02 — One file.** `llm.py` holds both claim extraction and adjudication —
same shape (a Claude call with a Pydantic output schema via
`messages.parse(output_format=...)`), so splitting them would buy a file,
not clarity.

**D-20 — Model.** `claude-opus-5` for both calls to start, per the plan.

**D-21 — Thinking + effort.** `thinking={"type": "adaptive"}`,
`output_config={"effort": "high"}` on every call. Verified against the
current API (not recalled from training) — Opus 5 runs thinking on by
default, `effort` is nested under `output_config` alongside `format`, and
`messages.parse()` accepts `output_format` and `output_config` as
independent parameters, so requesting structured output and tuning effort
don't conflict.

**D-22 — One chunk at a time.** `adjudicate(claim, chunk_text)` takes a
single chunk, not all `top_k` at once — source separation (not blending
what Cursor's docs say with what Codex's say) is the entire point of this
project, and batching chunks into one call would let the model do exactly
that blending.

**D-23 — Verbatim quote, verified.** `adjudicate()` checks
`result.quote in chunk_text` itself and retries (up to `MAX_RETRIES`) on a
quote that doesn't verify, salting the cache key per attempt so a retry
isn't just replaying the same bad cached answer. Exhausting retries raises
rather than returning a best-effort guess — a fabricated-looking citation
is the failure that would most embarrass this project, so silently
accepting an unverified quote was never on the table.

**D-24 — Prompt caching.** `cache_control: {"type": "ephemeral"}` on the
adjudication system prompt, which is byte-identical across every
(claim, chunk) call — this is the prompt caching actually pays for, since
adjudication runs once per retrieved chunk per claim while extraction runs
once per submission.

**D-25 — Output schemas.** Two Pydantic models,
`ExtractedClaims{claims: list[str]}` and
`Adjudication{relation: Literal[...], quote: str, confidence: float}`.

**D-26 — Where "mark it error" actually lives.** The plan called for
"3 retries, then mark the claim error." `llm.py`'s functions raise after
exhausting retries (API failures and unverified quotes alike) rather than
returning an "error" sentinel themselves — `Adjudication.relation` is a
strict 3-value `Literal` sent to the model as its output schema, and adding
a 4th value the model could pick from would blur the line between "Claude
judged this" and "our own retry loop gave up." Turning an exception into a
claim-level "error" row is deliverable D's job (`check.py`), not C's.

**D-37 — Response cache.** `llm_cache.jsonl`, keyed by
`sha256(model + system + messages + schema name [+ a retry salt])`. Lands
in C as the plan intended — every call made while building and testing C
(and later D, E) replays for free instead of being re-billed, and the cache
is what makes an eval run reproducible once E exists.

**Not yet verified:** C's own acceptance criteria (claims come out at a
sensible granularity; every returned quote is confirmed as a real substring
across real usage, not just the smoke test) needs a real `ANTHROPIC_API_KEY`
to run against — pending as of this entry.

## Appendix: pre-pivot decisions (Arthurian corpus, superseded)

Kept for provenance — these describe a corpus that no longer exists in this
repo, not current behavior.

**D-06 (orig) — Chunk unit.** Paragraph-bounded, target max ~200 words, a
single over-cap paragraph kept whole rather than split.

**D-07 (orig) — Chunk overlap.** None, to avoid double-counted evidence.

**D-08 (orig) — Gutenberg boilerplate.** Stripped via `*** START/END ***`
markers, with an assertion that they fired for every source except a
hand-extracted excerpt that never had them.

**D-09 (orig) — Locator format.** `source_id` + paragraph index range + char
span into the boilerplate-stripped text.

**D-10 (orig) — Chunk ID.** `sha256(source_id + text)[:16]`.

**D-11 (orig) — Storage.** Split `chunks.jsonl` + `embeddings.npy`.

**Corpus (orig).** Four public-domain texts from Project Gutenberg —
`geoffrey_of_monmouth` (hand-extracted from #37848, no standalone release
exists), `mabinogion` (#5160), `malory` (#46853), `tennyson` (#610) — tiered
1-4 by date of original composition, tier 0 reserved for a decisions ledger
that was never built.
