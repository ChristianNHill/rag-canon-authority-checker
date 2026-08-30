import argparse

from . import acquire, check, embed, eval as eval_, ingest, retrieve


def _run_check(tool, passage_path):
    passage = open(passage_path, encoding="utf-8").read()
    results = check.run(tool, passage)
    for r in results:
        print(f"\nClaim: {r['claim']}")
        flag = " [NEEDS REVIEW]" if r["needs_review"] else ""
        print(f"  -> {r['verdict'].upper()}{flag}")
        for w in r["winners"]:
            mismatch = " [cross-tool]" if w["tool"] != tool else ""
            print(f"     [{w['tool']} tier={w['tier']}]{mismatch} {w['relation']} "
                  f"({w['confidence']:.2f}) :: {w['quote']!r}")


def _run_eval():
    results, summary = eval_.run()
    for stratum, stats in summary.items():
        nr = f"{stats['needs_review_accuracy']:.0%}" if stats["needs_review_accuracy"] is not None else "n/a"
        cite = f"{stats['citation_plausibility_rate']:.0%}" if stats["citation_plausibility_rate"] is not None else "n/a"
        print(f"{stratum:20s} n={stats['n']:2d}  verdict={stats['verdict_accuracy']:.0%}  "
              f"needs_review={nr}  citation_plausible={cite}")
    print()
    for r in results:
        if not r["verdict_correct"] or r["citation_plausible"] is False or r["needs_review_correct"] is False:
            print(f"MISS  {r['id']:20s} expected={r['expected_verdict']:12s} "
                  f"actual={r['actual_verdict']:12s} citation_plausible={r['citation_plausible']}")


def main():
    parser = argparse.ArgumentParser(prog="ragcanon")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("acquire", help="fetch docs -> data/<tool>/... + manifest.jsonl")
    sub.add_parser("ingest", help="chunk vendored docs -> chunks.jsonl")
    sub.add_parser("embed", help="local embeddings -> embeddings.npy")
    retrieve_parser = sub.add_parser("retrieve", help="cosine top-k for a query string")
    retrieve_parser.add_argument("query")
    check_parser = sub.add_parser("check", help="extract claims from a passage and adjudicate each against retrieved evidence")
    check_parser.add_argument("tool", choices=["claude_code", "cursor", "codex"])
    check_parser.add_argument("passage_path")
    sub.add_parser("eval", help="score the golden set -> per-stratum accuracy")
    args = parser.parse_args()

    if args.command == "acquire":
        acquire.run()
    elif args.command == "ingest":
        ingest.run()
    elif args.command == "embed":
        embed.run()
    elif args.command == "retrieve":
        chunks, matrix = retrieve.load_index()
        for r in retrieve.retrieve(args.query, chunks, matrix):
            print(f"{r['score']:.3f}  [{r['tool']} tier={r['tier']}]  {r['locator']['path']} :: {r['locator']['heading_path']}")
    elif args.command == "check":
        _run_check(args.tool, args.passage_path)
    elif args.command == "eval":
        _run_eval()
