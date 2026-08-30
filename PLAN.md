# Plan update: pivot to AI coding agent documentation

## Context

The original plan (Arthurian legend as a self-contradicting corpus) proved the
mechanism: a resolver that ranks conflicting sources by configurable
authority. That domain was always a stand-in. The real target is documentation
for three AI coding agents — **Claude Code, Cursor, Codex** — one category,
three tools, so the comparison is real. Their docs go stale in weeks and
guidance written for one gets applied to another; that's the contradiction
surface this system now works on.

This repurposes `rag-canon-authority-checker` in place: same architecture
(retrieval → adjudicate → resolve, tier-based authority, pure resolver as the
product), new corpus, updated schema. The Arthurian data, `sources.yaml`, and
`DECISIONS.md` entries get replaced as part of implementing this; the
architecture and package (`ragcanon`) don't change.

**Explicitly out of scope:** model-provider API documentation (Anthropic's
Messages API, OpenAI's API docs). Different category — comparing a CLI tool's
docs against an API endpoint's docs produces meaningless findings. Where a
page covers both an agent tool and something out of scope, only the in-scope
portion is vendored, and that filtering is noted per-source.

## Two properties the corpus must preserve

1. **Real contradictions alongside planted ones.** All three tools have been
   renamed and restructured; there's a large body of guidance that was correct
   when written and is wrong now. The golden set (deliverable E) scores real
   found cases separately from planted ones.
2. **Cross-tool confusion is its own failure mode** — a statement can be
   simply wrong, or right for a different tool. Resolved below as an
   attribute derived from the schema, not a fourth verdict state.

## Schema (per chunk)

| Field | Notes |
|---|---|
| `tool` | `claude_code` \| `cursor` \| `codex` |
| `tier` | 1-4, source-type authority within that tool (see below) — uniform scheme across all three tools |
| `source` | citable origin: file/page path or URL, specific enough to link back to |
| `date_or_version` | vendor-date proxy for doc pages (acquisition date); real date/version for changelog entries, where it's free |
| `superseded_by` | null, or a pointer — populated **only** where the source text explicitly says so (regex-catchable "deprecated in favor of X" language). Broader supersession-linking is deferred to a later enrichment pass, not an ingest-time promise — matches the original plan's A/D boundary of staying deterministic and keyless. |

**Tiers (5 named, tier 5 not populated in this build):**

1. Official reference documentation
2. Release notes / changelogs
3. First-party cookbooks & example repos
4. First-party engineering blog posts
5. Community content — **skipped for this build** (bulk pull is ToS-blocked on
   all three platforms anyway; revisit only if the golden set shows a real
   gap official/changelog/cookbook/blog content can't cover)

**"Superseded" is not a 6th tier.** A stale official doc is still
official-reference in provenance, just not current — collapsing that into
the lowest tier conflates authority-of-source with currency-of-content.
Recency/supersession is a **second axis** the resolver (deliverable D) checks
alongside tier, not a tier level. Exact override rule (when does a newer
lower-tier source beat an older higher-tier one) is a D decision, made against
real evidence rows, same discipline as the original plan's confidence
thresholds.

**Cross-tool confusion** is a derived check in the resolver, not new
adjudication output: every chunk already carries `tool`; comparing it against
the submission's tagged target tool is a plain equality check `resolve()` can
do for free. No new LLM judgment call, no schema change to the adjudication
output. **Submissions must explicitly tag which tool they're about** — no
tool-classification step. Retrieval stays **tool-blind**, for the same reason
it stayed tier-blind before: filtering to only the "target tool" upstream
would make "guidance for Cursor got misapplied to Claude Code" unreachable,
since the Claude-Code-side evidence that reveals the mismatch would never get
retrieved.

## Per-tool acquisition

No corpus-size cap — each tool is vendored as fully as reachable; the
resulting size imbalance (Claude Code's official corpus runs roughly an order
of magnitude larger than the other two) is a fact about the world, handled in
retrieval config (deliverable B: per-tool `top_k`, or retrieve-per-tool-then-
merge) rather than by trimming. Community tier skipped for all three (see
above).

**Claude Code**
- Official docs: `llms-full.txt` (single concatenated file, all 131 pages, ~2.1M tokens) — Anthropic ships this specifically for ingestion, no scraping.
- Changelog: `CHANGELOG.md` from `anthropics/claude-code` (~147K tokens, 203 tagged releases, near-daily updates) — richest source of real "correct when written, wrong now" material.
- Cookbooks: `anthropics/claude-code-action`, `claude-code-base-action`, `claude-code-security-review`, `claude-plugins-official`, `claude-agent-sdk-demos`, `claude-code-monitoring-guide`, `code-migration-kit-with-claude-code`, `devcontainer-features`, `launch-your-agent` — READMEs.
- Blog: ~5-8 posts on anthropic.com/engineering. Two (Agent SDK, containment) cover other products too — take only the Claude-Code-specific portions, note the filtering.

**Cursor**
- Official docs: every `docs.cursor.com` page has a `.md` twin; `cursor.com/llms.txt` indexes ~150-200 pages across core docs, CLI docs, and a ~100+ page Help Center. **Help Center needs the same page-by-page filter as Codex** (below) — onboarding/features/security/troubleshooting are in scope, billing/account-admin content is not.
- Product API docs (Cloud Agents API, Admin API, Analytics API): in scope — this is Cursor's own product surface, not a model-provider API — but peripheral/lower priority.
- Changelog: no bulk export, paginated HTML at `cursor.com/changelog`. **Ingest all of it** (decided) — depth isn't large enough to warrant a cutoff, and this is where the `.cursorrules`→`.cursor/rules/*.mdc` and "Composer"→"Agent" rename history lives.
- Cookbooks: `github.com/cursor/plugins` — thin, that's the whole first-party set.
- Blog: `cursor.com/blog` — modest volume, genuine engineering content.

**Codex**
- Official docs: `learn.chatgpt.com/docs/codex/*`, `.md` twins + `llms.txt`. This tree is OpenAI's **shared ChatGPT-agent hub** — mixed in with Pets, Voice, Image gen, Browser extension, Computer use, Automations. **Page-by-page filter against `llms.txt` titles/paths** (cheap classification, no full-page fetch, no LLM) down to the ~45-55 actually coding-agent-scoped pages (CLI, IDE, config, AGENTS.md, subagents, sandboxing, MCP server, GitHub Action, code review, security); spot-check boundary cases.
- Changelog: `/codex/changelog`, same shared-scope filter applied to entries. Contains a clean real example: `codex mcp-server` deprecated in favor of "the Codex app server."
- Cookbooks: `github.com/openai/codex` (README, `docs/`, `AGENTS.md`, `CHANGELOG.md`, `SECURITY.md`) — cleanly scoped already, no filtering needed.
- Blog: not yet enumerated — to do during acquisition.
- **Known hazard, not an acquisition problem**: the name "Codex" was reused. A 2021 code-completion model of the same name was killed in 2023, unrelated to the 2025 coding agent. Both official sources used here (`developers.openai.com/codex`, `github.com/openai/codex`) are current-product sources, so this shouldn't surface from vendoring — flagging in `DECISIONS.md` as a known collision risk in case blog enumeration turns up pre-2025 "Codex" content that needs excluding rather than mistakenly vendored as an early version of the same product.

## Chunking (deliverable A)

Paragraph-bounded chunking (the Arthurian approach) doesn't fit markdown
structure — it would split code fences and tables mid-way. New approach:

- **Section-bounded**: split at markdown headers (H2/H3). A section that
  exceeds the same ~200-300 word soft cap falls back to paragraph-bounded
  splitting within it (same rule as before: never split a paragraph, and now
  also never split a code fence).
- **Changelog entries are one chunk each**, regardless of size — each dated
  entry is already the natural atomic unit, no grouping heuristic needed.
- **Locator format changes**: `source path/URL + heading path + char span`
  (e.g. `cli-reference.md > Flags > --dangerously-skip-permissions`) replaces
  paragraph-index, since a raw paragraph number means nothing for a doc
  citation the way it did for prose.
- **Chunk ID**: same content-hash approach as before —
  `sha256(tool + source_id + text)`, stable across re-ingest.

## Deferred / explicitly not decided here

- Exact recency-vs-tier override rule in `resolve()` — a D decision, made
  against real evidence rows.
- Whether/how to backfill `superseded_by` beyond explicit textual mentions.
- Per-page real `date_or_version` (would require pulling git history from doc
  source repos separately) — vendor-date proxy is the default until shown
  insufficient.
- Codex blog enumeration — not yet done.
- Retrieval-layer handling of the cross-tool size imbalance (deliverable B).
