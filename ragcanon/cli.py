import argparse

from . import acquire, check, embed, ingest, retrieve


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
