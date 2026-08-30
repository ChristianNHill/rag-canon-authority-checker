# Documentation consistency checking across AI coding agents

## Why this repo exists

A weekend exploration, I built this to get hands-on with a full retrieval pipeline: getting a corpus in, grounding claims against it, deciding what counts as correct, measuring how often the system gets it right, routing the uncertain cases to a person, and feeding what that person decides back into the system.

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

Tiers 4 and 5 are defined in the schema but not populated in this pass. Blog posts need per-post scope filtering that wasn't worth doing before the resolver exists to use them. Community content (Reddit, forums) can't be bulk-pulled under any of the three platforms' terms of service. Both are candidates to add later if the evaluation shows a real gap official/changelog/cookbook content can't cover.

The tier ordering lives in a policy file rather than in code, so it can be changed and the whole evaluation rerun. That is deliberate: which sources outrank which is a decision an organization makes, not a property of the data.

Corpus size by tool (current as of this ingest):

| Tool | Documents | Chunks |
|---|---|---|
| Claude Code | 201 | 6,338 |
| Cursor | 162 | 2,357 |
| Codex | 234 | 1,308 |
| **Total** | **597** | **10,003** |

Claude Code's share is larger by design, not by accident. Anthropic ships a single file specifically for LLM ingestion that the other two tools don't have an equivalent of. The imbalance is handled at retrieval time (below), not by trimming the corpus to match.

## Pipeline

Built so far:

1. **Acquire**: fetch each tool's documentation from its own sources (official docs, changelogs, cookbook repos), filtered to exclude out-of-scope content (a shared docs hub that also covers unrelated consumer features, in Codex's case).
2. **Ingest**: chunk each document (section-bounded, code-fence- and table-aware), assign a locator (heading path + exact character span) and a content-hash ID.
3. **Embed**: local sentence-transformer embeddings, cached by chunk ID so re-ingesting unchanged content costs nothing.
4. **Retrieve**: cosine similarity, top-k per tool rather than one flat top-k, so no tool's evidence crowds out another's.
5. **Extract claims**: pull individual, checkable claims out of a submitted passage.
6. **Adjudicate**: for each (claim, chunk) pair, judge supports / contradicts / irrelevant with a verbatim, verified quote.
7. **Resolve**: turn the adjudicated evidence for one claim into a single verdict, using source authority to pick a winner when the evidence disagrees.

The review-queue loop (a person adjudicating flagged findings and feeding that back into the golden set and the policy file) is still ahead.

## Design decisions

The decisions below shaped the system more than any implementation detail did. Each one had a defensible alternative.

**Verdict states.** Four, not three: confirmed, contradicted, conflicting, and not established. Not established stays separate from confirmed and contradicted because no evidence found is a coverage gap in the corpus, not a verdict about the claim. Conflicting stays separate from contradicted for the same reason: when the top-authority sources disagree with each other, the docs are unsettled, and that is a different problem from the passage being wrong. Collapsing either into a neighboring state would route the finding to the wrong follow-up.

**Wrong versus wrong-for-this-tool.** A claim can be incorrect, or it can be correct for a different agent than the one under discussion. This became an attribute, not a fourth verdict state: every chunk already carries which tool it belongs to, so comparing that against the tool the submission is tagged with is a plain equality check the resolver can do for free. No separate model judgment call is needed. Retrieval stays tool-blind for the same reason it stays tier-blind: filtering to only the "target tool" upstream would make a cross-tool-confusion finding unreachable in the first place.

**Recency against authority.** A recent changelog can outrank older official reference documentation, so tier alone does not resolve a conflict. Settled so far: this is a second axis the resolver checks alongside tier, not a sixth, lowest tier. Collapsing "superseded" into the bottom of the tier list would conflate authority-of-source with currency-of-content.

The exact rule follows from what the corpus contains rather than an arbitrary cutoff. A source that explicitly marks itself as superseded always loses, regardless of tier or date, since the source is disclaiming itself. Otherwise, recency decides only when both competing sources carry a real date, not the ingest-time proxy date most doc pages get. Only changelog entries and Claude Code's dated digest pages carry a real date. Most tier comparisons have nothing to compare dates against in the first place, so tier decides instead.

**Confidence threshold.** Not every flag is worth a person's attention. A conflicting verdict always goes to review, since it is definitionally ambiguous. A confirmed or contradicted verdict goes to review only if the winning evidence's own confidence score falls below 0.7. That number is a placeholder, chosen for lacking anything better: there was no golden set yet to calibrate it against. Now that one exists, it is the first thing worth revisiting.

**Chunking.** Section-bounded, not fixed-size or paragraph-bounded: a chunk never crosses a heading boundary, and within a section, text is grouped up to a soft word cap. Two things don't split under any circumstance: a code fence and a markdown table row, because a citation that cuts a code block or a table row in half isn't quotable. The tradeoff against paragraph-bounded chunking (the simpler alternative) is a small amount of extra parsing complexity in exchange for citations that make sense for structured documentation instead of prose.

## Evaluation

The golden set is the part of this repo I would point at first.

Cases are stratified so a single aggregate number cannot hide the interesting result:

- **Hard contradictions**: the claim conflicts with every tier
- **Soft contradictions**: the claim conflicts with the primary source but a lower tier supports it
- **Conflicting**: the top-authority sources disagree with each other, a problem with the docs rather than the claim
- **Cross-tool**: the claim is correct, for a different agent
- **Not established**: the documentation neither supports nor contradicts it
- **Clean**: no problem at all, included to measure false positives

Cases come from two places. Some are planted, written to test a specific failure mode. Others are real contradictions found in the corpus, which exist because these products have been renamed and restructured. The harness scores both and reports them separately, because a system that catches planted contradictions and misses real ones has not been evaluated.

Scoring uses two modes chosen per case. I check the verdict and the review-routing decision by exact match, against a value I derived by reading the corpus text myself. I never ran the system and copied its own output as the expected value, since that would only check the system against itself. I check the winning citation differently: a judge decides whether the quote plausibly justifies the claimed relation, rather than matching it against one hand-picked source. Real evidence often has more than one chunk that would correctly justify the same verdict, so exact-matching a citation would penalize a legitimate alternative. Sending a claim with one correct answer to a model judge is slower and less reliable than checking it directly. So the verdict itself never gets a judge; only the reasoning behind it does.

The golden set has grown to thirteen cases across the six strata above. Cross-tool and soft contradiction stay at one case each: both turned out to be the hardest strata to find organically, since the corpus doesn't populate the blog and community tiers yet, and cookbook-tier content is mostly internal engineering convention, not the kind of user-facing claim that would meaningfully conflict with an official doc. The soft contradiction case is planted rather than found, built from a real, verified fact rather than invented from nothing. Growing those two strata further, especially with more found real cases, is the natural next step.

## Results

Second run, 2026-08-30, against the thirteen-case golden set (up from nine). These counts are still too small to read as a real precision and recall number, so I'm reporting them as raw per-stratum results rather than dressing them up as statistics:

| Stratum | n | Verdict correct | Needs-review correct | Citation plausible |
|---|---|---|---|---|
| Hard contradiction | 3 | 3/3 | n/a | 2/3 |
| Conflicting | 2 | 2/2 | 2/2 | 2/2 |
| Cross-tool | 1 | 1/1 | n/a | 1/1 |
| Soft contradiction | 1 | 1/1 | n/a | 1/1 |
| Not established | 3 | 2/3 | n/a | 0/1 |
| Clean | 3 | 3/3 | 1/1 | 3/3 |

Eleven of thirteen verdicts landed correctly. The four new cases all landed clean; both misses are the same two from the first run, which is a good sign for reproducibility rather than a bad one. Both are real and worth reading, not noise, which is the point of the next section.

## Where it fails

**A right verdict resting on a weak citation.** The claim was that Claude Code's 1M-token context window for Sonnet 4.5 is available on the Max plan. The system correctly called this contradicted, but the quote it cited to justify that was about Sonnet 4.6, not 4.5, and about needing extra usage credits, not about availability on Max as such. The verdict itself was right for other reasons visible elsewhere in the evidence, but this particular citation is a weaker link than it looks, which is exactly what the citation judge is supposed to catch and exact-match verdict scoring alone would have missed entirely.

**A golden-set label that turned out to be wrong.** I wrote a not-established case claiming Claude Code can split a large refactor into multiple pull requests based on a file dependency graph, expecting no evidence either way. I was wrong: `/batch` does something adjacent. The system found it at 0.55 confidence and returned confirmed. But the citation judge flagged the citation as implausible, correctly: `/batch` doesn't split by a dependency graph, so the claim's specific mechanism isn't established even though the general shape of the feature is real. The confidence score, 0.55, below the 0.7 threshold, routed this to human review regardless of the verdict, which is the behavior that matters here: a low-confidence match gets sent to a person rather than asserted outright.

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

I haven't built any of this yet. It's the natural next step after the golden set: a real review queue needs somewhere to write those adjudications and a decisions ledger, beyond a design for one.

## Running it

What works today:

```bash
pip install -e ".[dev]"

python -m ragcanon acquire   # fetch docs for all three tools -> data/, manifest.jsonl
python -m ragcanon ingest    # chunk everything -> chunks.jsonl
python -m ragcanon embed     # local embeddings -> embeddings.npy (cached by chunk ID)
python -m ragcanon retrieve "how do I configure MCP servers"   # cosine top-k, per tool

python -m ragcanon check claude_code samples/passage.md
# extracts claims from the passage, resolves each into a verdict against retrieved evidence

python -m ragcanon eval
# scores golden_set.jsonl, reports accuracy per stratum
```

Needs a `.env` with `ANTHROPIC_API_KEY` for `check` and `eval`; nothing else calls a paid API. `pytest` runs the test suite (pure logic gets real tests; anything that calls an API gets a smoke test, skipped without a key).

I ran all of this through headless Claude Code rather than typing commands by hand. A prompt like `claude -p "run python -m ragcanon check claude_code samples/passage.md and report the verdicts"` drives the same CLI non-interactively. That's how the acquisition, ingestion, and eval runs behind the results above happened.

The review queue, where a person adjudicates flagged findings and that adjudication feeds back into the golden set and the policy file, is still ahead.

## What I would do differently in production

The corpus is a snapshot. Nothing here re-acquires or re-ingests on a schedule. The moment a real team adopted this, the first question would be how often to refresh it. A close second would be how to detect that a chunk's underlying page moved before someone notices a stale answer. Retrieval is a flat `numpy` matrix multiply, which is fine at ten thousand chunks and won't be at ten million. A real deployment would need an actual vector index long before the corpus grew that large.

The review queue as designed assumes one reviewer working through a queue in order. A real team needs assignment, ownership, and a way to avoid two people adjudicating the same finding at once. And the policy file is versioned in name only right now: nothing tracks which policy version produced which past verdict, so a tier reordering or a new confidence threshold would make old adjudications incomparable to new ones, with no record that the change happened or that anyone decided it on purpose.

None of this shows up until the system is in use. That's the real argument for treating the golden set and the review queue as living things rather than a one-time eval.

## Notes

Built through agentic coding workflows. The architectural decisions, the tier ordering, the verdict taxonomy, the golden-set cases, and the scoring design are mine.

Corpus is public vendor documentation. No proprietary or client material.
