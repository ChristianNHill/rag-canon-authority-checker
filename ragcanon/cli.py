import argparse

from . import acquire, embed, ingest, llm, retrieve


def _run_check(tool, passage_path):
    passage = open(passage_path, encoding="utf-8").read()
    claims = llm.extract_claims(passage, tool)
    print(f"{len(claims)} claims extracted:")
    chunks, matrix = retrieve.load_index()
    for claim in claims:
        print(f"\nClaim: {claim}")
        for r in retrieve.retrieve(claim, chunks, matrix, top_k_per_tool=3):
            adj = llm.adjudicate(claim, r["text"])
            print(f"  [{r['tool']} tier={r['tier']}] {adj.relation} ({adj.confidence:.2f}) :: {adj.quote!r}")


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
