"""Deliverable A: chunk vendored docs -> chunks.jsonl.

Section-bounded chunking (never split a paragraph or a code fence, flush at
every H2/H3 heading), heading-path + char-span locators, content-hash chunk
IDs. Changelog documents (`chunking: "changelog_entries"`) split one chunk
per dated entry instead, regardless of size.
"""
import hashlib
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
MANIFEST = ROOT / "manifest.jsonl"
CHUNKS_OUT = ROOT / "chunks.jsonl"

# ponytail: a long bullet/numbered list with no blank lines between items is
# one atomic "paragraph" block like any other, so a changelog's PR-link list
# can push a single chunk past the cap (observed up to ~3.6K words). Same
# fix as the table case below (split by list item) if this shows up as a
# real retrieval/adjudication problem.
MAX_CHUNK_WORDS = 250
_SECTION_LEVELS = (2, 3)  # H2/H3 force a chunk flush; H1/H4+ don't

_HEADING_RE = re.compile(r"^(#{1,6})\s+(.*)$")
_FENCE_RE = re.compile(r"^\s*```")
_TABLE_SEP_RE = re.compile(r"^\s*\|?\s*:?-{2,}:?\s*(\|\s*:?-{2,}:?\s*)+\|?\s*$")
_SUPERSEDED_RE = re.compile(
    r"\b(?:deprecated|removed)\b.{0,60}?"
    r"(?:in favor of\s+(?P<a>.{1,80}?)(?=[.]|$)"
    r"|replaced by\s+(?P<b>.{1,80}?)(?=[.]|$)"
    r"|\.\s*Use\s+(?:the\s+)?(?P<c>.{1,80}?)\s+instead\b)",
    re.IGNORECASE,
)


def load_manifest():
    with open(MANIFEST, encoding="utf-8") as f:
        return [json.loads(line) for line in f if line.strip()]


def _trim_blank_edges(lines, start, end):
    while start < end and lines[start].strip() == "":
        start += 1
    while end > start and lines[end - 1].strip() == "":
        end -= 1
    return start, end


def _append_paragraph(lines, blocks, start, end):
    """Append a trimmed paragraph -- splitting a markdown table into one
    block per row, since a table is otherwise one giant blank-line-free
    "paragraph" that would stay an indivisible multi-thousand-word block."""
    start, end = _trim_blank_edges(lines, start, end)
    if start >= end:
        return
    if end - start >= 2 and "|" in lines[start] and _TABLE_SEP_RE.match(lines[start + 1]):
        blocks.append({"type": "text", "start_line": start, "end_line": start + 2})
        for r in range(start + 2, end):
            blocks.append({"type": "text", "start_line": r, "end_line": r + 1})
        return
    blocks.append({"type": "text", "start_line": start, "end_line": end})


def _classify_line(line, in_fence):
    if in_fence:
        return "fence_end" if _FENCE_RE.match(line) else "in_fence"
    if _FENCE_RE.match(line):
        return "fence_start"
    if _HEADING_RE.match(line):
        return "heading"
    if line.strip() == "":
        return "blank"
    return "text"


def _parse_blocks(text):
    """Ordered blocks: {type: heading|text, level?, title?, start_line, end_line}."""
    lines = text.split("\n")
    blocks = []
    in_fence = False
    fence_start = None
    para_start = None

    def close_paragraph(at):
        nonlocal para_start
        if para_start is not None:
            _append_paragraph(lines, blocks, para_start, at)
            para_start = None

    for i, line in enumerate(lines):
        kind = _classify_line(line, in_fence)
        if kind == "in_fence":
            continue
        if kind == "fence_end":
            blocks.append({"type": "text", "start_line": fence_start, "end_line": i + 1})
            in_fence, fence_start = False, None
        elif kind == "fence_start":
            close_paragraph(i)
            in_fence, fence_start = True, i
        elif kind == "heading":
            close_paragraph(i)
            m = _HEADING_RE.match(line)
            blocks.append({
                "type": "heading", "level": len(m.group(1)), "title": m.group(2).strip(),
                "start_line": i, "end_line": i + 1,
            })
        elif kind == "blank":
            close_paragraph(i)
        elif para_start is None:
            para_start = i

    close_paragraph(len(lines))
    if in_fence:
        blocks.append({"type": "text", "start_line": fence_start, "end_line": len(lines)})
    return blocks, lines


def _line_offsets(lines):
    """Char offset of the start of each line, as if lines were '\\n'-joined."""
    offsets = [0]
    for line in lines:
        offsets.append(offsets[-1] + len(line) + 1)
    return offsets


def make_chunks(text, max_words=MAX_CHUNK_WORDS):
    blocks, lines = _parse_blocks(text)
    line_offset = _line_offsets(lines)

    def block_text(b):
        start, end = line_offset[b["start_line"]], line_offset[b["end_line"]] - 1
        return text[start:end], start, end

    chunks = []
    heading_stack = []  # list of (level, title)
    buf = []  # list of (block, block_text, start, end)
    buf_words = 0

    def flush():
        nonlocal buf, buf_words
        if not buf:
            return
        char_start, char_end = buf[0][2], buf[-1][3]
        chunks.append({
            "text": text[char_start:char_end],
            "heading_path": " > ".join(t for _, t in heading_stack),
            "char_start": char_start,
            "char_end": char_end,
        })
        buf, buf_words = [], 0

    for b in blocks:
        if b["type"] == "heading":
            if b["level"] in _SECTION_LEVELS:
                flush()
            while heading_stack and heading_stack[-1][0] >= b["level"]:
                heading_stack.pop()
            heading_stack.append((b["level"], b["title"]))
            btext, start, end = block_text(b)
            buf.append((b, btext, start, end))
            buf_words += len(btext.split())
            continue

        btext, start, end = block_text(b)
        words = len(btext.split())
        if buf and buf_words + words > max_words:
            flush()
        buf.append((b, btext, start, end))
        buf_words += words

    flush()
    return chunks


def _split_changelog_entries(text):
    """One chunk per top-level '## ' entry, whole entry, no size cap."""
    starts = [m.start() for m in re.finditer(r"(?m)^## ", text)]
    if not starts:
        return [{"text": text, "heading_path": "", "char_start": 0, "char_end": len(text)}]
    starts.append(len(text))
    entries = []
    for i in range(len(starts) - 1):
        s, e = starts[i], starts[i + 1]
        while e > s and text[e - 1] == "\n":
            e -= 1
        title = text[s:text.index("\n", s) if "\n" in text[s:e] else e].lstrip("# ").strip()
        entries.append({"text": text[s:e], "heading_path": title, "char_start": s, "char_end": e})
    return entries


def _detect_superseded_by(text):
    # Flatten whitespace first: a wrapped markdown link ("[Codex app\nserver]")
    # would otherwise break mid-match since the source is hard-wrapped prose.
    flat = re.sub(r"\s+", " ", text)
    m = _SUPERSEDED_RE.search(flat)
    if not m:
        return None
    val = m.group("a") or m.group("b") or m.group("c")
    return val.strip().rstrip(").,;") if val else None


def run():
    manifest = load_manifest()
    all_chunks = []
    by_tool = {}

    for doc in manifest:
        text = (ROOT / doc["path"]).read_text(encoding="utf-8")
        if doc["chunking"] == "changelog_entries":
            raw_chunks = _split_changelog_entries(text)
        else:
            raw_chunks = make_chunks(text)

        for rc in raw_chunks:
            chunk_id = hashlib.sha256(
                f"{doc['tool']}\x1f{doc['path']}\x1f{rc['text']}".encode()
            ).hexdigest()[:16]
            all_chunks.append({
                "chunk_id": chunk_id,
                "tool": doc["tool"],
                "tier": doc["tier"],
                "source": doc["source"],
                "date_or_version": doc.get("date_or_version"),
                "superseded_by": _detect_superseded_by(rc["text"]),
                "text": rc["text"],
                "locator": {
                    "path": doc["path"],
                    "heading_path": rc["heading_path"],
                    "char_start": rc["char_start"],
                    "char_end": rc["char_end"],
                },
            })
        by_tool[doc["tool"]] = by_tool.get(doc["tool"], 0) + len(raw_chunks)

    with open(CHUNKS_OUT, "w", encoding="utf-8") as f:
        for chunk in all_chunks:
            f.write(json.dumps(chunk, ensure_ascii=False) + "\n")

    print(f"{len(manifest)} documents, {len(all_chunks)} chunks -> {CHUNKS_OUT}  ({by_tool})")
    return all_chunks
