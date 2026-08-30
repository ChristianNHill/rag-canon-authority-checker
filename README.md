# Documentation consistency checking across AI coding agents

## Why this repo exists

I built this to get hands-on with a full retrieval pipeline rather than the retrieval step alone: getting a corpus in, grounding claims against it, deciding what counts as correct, measuring how often the system gets it right, routing the uncertain cases to a person, and feeding what that person decides back into the system.

Retrieval on its own is the easy half and the well-documented half. The parts I wanted practice with are the ones that come after: what happens when the sources disagree, how you know whether the output is any good, and what a human adds that the system cannot.

## The problem

Documentation for AI coding agents goes stale in weeks. Features ship, get renamed, get deprecated. Guidance written for one tool gets applied to another, because the tools solve the same problems with different mechanisms.

So when someone writes "configure the agent this way," the question is which tool that is right for, according to which source, and whether that source is still current.

This system takes a passage, pulls out the individual claims, and retrieves the documentation bearing on each one. It then reports what conflicts, what it conflicts with, and how authoritative that conflict is.

## Corpus

Documentation for three AI coding agents: Claude Code, Cursor, and Codex.

Every chunk carries the tool it belongs to, an authority tier, a source citation, and a date or version. Authority tiers in descending order:

1. Official reference documentation
2. Release notes and changelogs
3. First-party cookbooks and example repos
4. First-party engineering blog posts
5. Community content

Tiers 4 and 5 are defined in the schema but not populated in this pass — blog posts need per-post scope filtering that wasn't worth doing before the resolver exists to use them, and community content (Reddit, forums) can't be bulk-pulled cleanly under any of the three platforms' terms of service. Both are candidates to add later if the evaluation shows a real gap official/changelog/cookbook content can't cover.

The tier ordering lives in a policy file rather than in code, so it can be changed and the whole evaluation rerun. That is deliberate: which sources outrank which is a decision an organization makes, not a property of the data.

Corpus size by tool (current as of this ingest):

| Tool | Documents | Chunks |
|---|---|---|
| Claude Code | 201 | 6,338 |
| Cursor | 162 | 2,357 |
| Codex | 234 | 1,308 |
| **Total** | **597** | **10,003** |

Claude Code's share is larger by design, not by accident — Anthropic ships a single file specifically for LLM ingestion that the other two tools don't have an equivalent of. The imbalance is handled at retrieval time (below), not by trimming the corpus to match.

## Pipeline

Built so far:

1. **Acquire** — fetch each tool's documentation from its own sources (official docs, changelogs, cookbook repos), filtered to exclude out-of-scope content (a shared docs hub that also covers unrelated consumer features, in Codex's case).
2. **Ingest** — chunk each document (section-bounded, code-fence- and table-aware), assign a locator (heading path + exact character span) and a content-hash ID.
3. **Embed** — local sentence-transformer embeddings, cached by chunk ID so re-ingesting unchanged content costs nothing.
4. **Retrieve** — cosine similarity, top-k per tool rather than one flat top-k, so no tool's evidence crowds out another's.
5. **Extract claims** — pull individual, checkable claims out of a submitted passage.
6. **Adjudicate** — for each (claim, chunk) pair, judge supports / contradicts / irrelevant with a verbatim, verified quote.

[FILL IN: resolve (turning adjudicated evidence into a verdict), eval, and the review-queue loop — not yet built]

## Design decisions

The decisions below shaped the system more than any implementation detail did. Each one had a defensible alternative.

**Verdict states.** [FILL IN: how many states, what they are, and why "not established" earns its own state instead of collapsing into contradicted]

**Wrong versus wrong-for-this-tool.** A claim can be incorrect, or it can be correct for a different agent than the one under discussion. This became an attribute, not a fourth verdict state: every chunk already carries which tool it belongs to, so comparing that against the tool the submission is tagged with is a plain equality check the resolver can do for free — no separate model judgment call needed. Retrieval stays tool-blind for the same reason it stays tier-blind: filtering to only the "target tool" upstream would make a cross-tool-confusion finding unreachable in the first place.

**Recency against authority.** A recent changelog can outrank older official reference documentation, so tier alone does not resolve a conflict. Settled so far: this is a second axis the resolver checks alongside tier, not a sixth, lowest tier — collapsing "superseded" into the bottom of the tier list would conflate authority-of-source with currency-of-content. [FILL IN: the exact override rule — when a newer lower-tier source actually outranks an older higher-tier one — still needs deciding against real evidence rows]

**Confidence threshold.** Not every flag is worth a person's attention. [FILL IN: what a finding has to clear to surface, and how that number was chosen]

**Chunking.** Section-bounded, not fixed-size or paragraph-bounded: a chunk never crosses a heading boundary, and within a section, text is grouped up to a soft word cap. Two things don't split under any circumstance — a code fence and a markdown table row — because a citation that cuts a code block or a table row in half isn't quotable. The tradeoff against paragraph-bounded chunking (the simpler alternative) is a small amount of extra parsing complexity in exchange for citations that actually make sense for structured documentation instead of prose.

## Evaluation

The golden set is the part of this repo I would point at first.

Cases are stratified so a single aggregate number cannot hide the interesting result:

- **Hard contradictions**: the claim conflicts with every tier
- **Soft contradictions**: the claim conflicts with the primary source but a lower tier supports it
- **Cross-tool**: the claim is correct, for a different agent
- **Not established**: the documentation neither supports nor contradicts it
- **Clean**: no problem at all, included to measure false positives

Cases come from two places. Some are planted, written to test a specific failure mode. Others are real contradictions found in the corpus, which exist because these products have been renamed and restructured. The harness scores both and reports them separately, because a system that catches planted contradictions and misses real ones has not been evaluated.

Scoring uses [FILL IN: number] modes chosen per case: [FILL IN: the modes and when each applies]. Sending a claim with one correct answer to a model judge is slower and less reliable than checking it directly, so not every case gets a judge.

[FILL IN: none of this is built yet — golden set, scorer, and the stratified harness are still ahead]

## Results

[FILL IN: overall precision and recall, then broken out by stratum and by tool. Include the failures. A README reporting perfect scores is neither credible nor interesting.]

## Where it fails

[FILL IN: the specific cases it gets wrong and the pattern behind them. This section is the point of the eval.]

## Human in the loop

Findings above the confidence threshold go to a review queue. A reviewer adjudicates each one:

- **Confirmed**: a real conflict
- **Not a conflict**: the system was wrong
- **Intentional departure**: known, and this is the local convention
- **Unclear**: needs research, stays open

Adjudications feed back rather than sitting in a log:

- Confirmed and not-a-conflict verdicts become new golden set cases, with ground truth from a person instead of from me planting it. The golden set grows through use.
- Patterns in dismissals surface as suggested policy changes. If reviewers keep rejecting flags sourced from a given tier, that tier is ranked too high for this team.
- Intentional departures are written to a decisions ledger that is ingested at the highest authority tier. Once a team rules on something, the system checks against that ruling alongside the vendor documentation.

That last one is what makes this a tool a team could keep using rather than one that argues with them indefinitely.

[FILL IN: not built yet]

## Running it

What works today:

```bash
pip install -e ".[dev]"

python -m ragcanon acquire   # fetch docs for all three tools -> data/, manifest.jsonl
python -m ragcanon ingest    # chunk everything -> chunks.jsonl
python -m ragcanon embed     # local embeddings -> embeddings.npy (cached by chunk ID)
python -m ragcanon retrieve "how do I configure MCP servers"   # cosine top-k, per tool

python -m ragcanon check claude_code samples/passage.md
# extracts claims from the passage, adjudicates each against retrieved evidence
# (no verdict yet -- that's the resolver, not built)
```

Needs a `.env` with `ANTHROPIC_API_KEY` for `check`; nothing else calls a paid API. `pytest` runs the test suite (pure logic gets real tests; anything that calls an API gets a smoke test, skipped without a key).

[FILL IN: eval run, review queue -- not built yet]

## What I would do differently in production

This is an exploration, not a production system, and the gap between the two is worth naming.

[FILL IN: two or three paragraphs. Candidates: corpus freshness and reingestion, retrieval at a corpus size where numpy similarity stops being reasonable, review queue throughput with more than one reviewer, what happens when the policy file changes and prior adjudications no longer apply, and how you would know the system had degraded.]

## Notes

Built through agentic coding workflows. The architectural decisions, the tier ordering, the verdict taxonomy, the golden set, and the scoring design are mine.

Corpus is public vendor documentation. No proprietary or client material.
