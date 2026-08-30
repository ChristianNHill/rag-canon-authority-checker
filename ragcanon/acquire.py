"""Deliverable A (acquisition step): fetch docs for claude_code, cursor, codex.

Writes raw vendored files under data/<tool>/... and one manifest.jsonl row per
document: {path, tool, tier, source, date_or_version, chunking}. ingest.py
reads the manifest and chunks each file; this module only fetches and filters.

Tiers: 1 official reference, 2 changelog, 3 cookbook/example repo.
Tier 4 (blog) and 5 (community) are not populated in this pass -- see
DECISIONS.md.
"""
import json
import re
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
MANIFEST_OUT = ROOT / "manifest.jsonl"

_HEADERS = {"User-Agent": "ragcanon-acquire/0.1 (research corpus builder)"}


def _get(url, timeout=30):
    req = urllib.request.Request(url, headers=_HEADERS)
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read().decode("utf-8", errors="replace")


def _get_readme(owner_repo, timeout=30):
    last_error = None
    for branch in ("main", "master"):
        try:
            return _get(f"https://raw.githubusercontent.com/{owner_repo}/{branch}/README.md", timeout)
        except Exception as e:
            last_error = e
    raise RuntimeError(f"no README on main or master for {owner_repo}: {last_error}")


def _slug(url_path):
    slug = url_path.strip("/").replace("/", "__") or "index"
    return re.sub(r"[^a-zA-Z0-9_.-]", "-", slug)


def _run_phases(tool, *phases):
    """Run each acquisition phase, keeping rows from earlier phases even if
    a later one fails -- e.g. codex's changelog hitting a rate limit
    shouldn't discard the docs phase that already succeeded."""
    rows = []
    for phase in phases:
        try:
            rows += phase()
        except Exception as e:
            print(f"  {tool}: {phase.__name__} FAILED ({e}) -- keeping earlier {tool} phases")
    return rows


def _write(tool, subdir, name, text):
    out_dir = DATA / tool / subdir
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / name
    path.write_text(text, encoding="utf-8")
    return path.relative_to(ROOT).as_posix()


def _html_to_text(html, start_tag="<article"):
    start = html.find(start_tag)
    end = html.find("</article>", start)
    fragment = html[start:end] if start != -1 and end != -1 else html
    text = re.sub(r"<[^>]+>", " ", fragment)
    text = (text.replace("&amp;", "&").replace("&#x27;", "'").replace("&#39;", "'")
                .replace("&quot;", '"').replace("&lt;", "<").replace("&gt;", ">"))
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r" *\n *", "\n", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip() + "\n"


# ---------------------------------------------------------------- claude_code

_CC_LLMS_FULL = "https://code.claude.com/docs/llms-full.txt"
_CC_CHANGELOG = "https://raw.githubusercontent.com/anthropics/claude-code/main/CHANGELOG.md"
_CC_COOKBOOK_REPOS = [
    "anthropics/claude-code-action", "anthropics/claude-code-base-action",
    "anthropics/claude-code-security-review", "anthropics/claude-plugins-official",
    "anthropics/claude-agent-sdk-demos", "anthropics/claude-code-monitoring-guide",
    "anthropics/code-migration-kit-with-claude-code", "anthropics/devcontainer-features",
    "anthropics/launch-your-agent",
]
_WHATS_NEW_WEEK_RE = re.compile(r"/whats-new/(\d{4}-w\d{2})$")


def _split_llms_full(text):
    """(title, url, body) per page: a `# Title` line immediately followed
    (allowing blank lines) by `Source: <url>` starts a new page."""
    lines = text.split("\n")
    starts = []
    for i, line in enumerate(lines):
        if not line.startswith("# "):
            continue
        j = i + 1
        while j < len(lines) and lines[j].strip() == "":
            j += 1
        if j < len(lines) and lines[j].startswith("Source: https://"):
            starts.append((i, line[2:].strip(), lines[j][len("Source: "):].strip()))

    pages = []
    for k, (start, title, url) in enumerate(starts):
        end = starts[k + 1][0] if k + 1 < len(starts) else len(lines)
        body = "\n".join(lines[start:end]).strip() + "\n"
        pages.append((title, url, body))
    return pages


def acquire_claude_code():
    rows = []

    full = _get(_CC_LLMS_FULL)
    for title, url, body in _split_llms_full(full):
        path_part = urllib.parse.urlparse(url).path
        path = _write("claude_code", "docs", _slug(path_part) + ".md", body)
        m = _WHATS_NEW_WEEK_RE.search(path_part)
        rows.append({
            "path": path, "tool": "claude_code", "tier": 1, "source": url,
            "date_or_version": m.group(1) if m else None, "chunking": "sectioned",
        })
    print(f"  claude_code/docs: {len(rows)} pages")

    changelog = _get(_CC_CHANGELOG)
    path = _write("claude_code", "changelog", "CHANGELOG.md", changelog)
    rows.append({
        "path": path, "tool": "claude_code", "tier": 2,
        "source": "https://github.com/anthropics/claude-code/blob/main/CHANGELOG.md",
        "date_or_version": None, "chunking": "changelog_entries",
    })
    print(f"  claude_code/changelog: {len(re.findall(r'(?m)^## ', changelog))} entries")

    n_cookbook = 0
    for repo in _CC_COOKBOOK_REPOS:
        try:
            readme = _get_readme(repo)
        except Exception as e:
            print(f"  claude_code/cookbook: {repo} SKIPPED ({e})")
            continue
        path = _write("claude_code", "cookbook", repo.split("/")[1] + ".md", readme)
        rows.append({
            "path": path, "tool": "claude_code", "tier": 3,
            "source": f"https://github.com/{repo}",
            "date_or_version": None, "chunking": "sectioned",
        })
        n_cookbook += 1
    print(f"  claude_code/cookbook: {n_cookbook} repos")

    return rows


# --------------------------------------------------------------------- cursor

_CURSOR_LLMS = "https://cursor.com/llms.txt"
_CURSOR_EXCLUDE_PREFIXES = (
    "/docs/account/", "/docs/enterprise/",
    "/help/account-and-billing/", "/help/grok-bot/",
)
_CURSOR_COOKBOOK_REPO = "cursor/plugins"


def _cursor_doc_urls(llms_txt):
    urls = []
    for line in llms_txt.splitlines():
        m = re.match(r"\s*-\s*(https://cursor\.com\S+\.md)\s*$", line)
        if m:
            urls.append(m.group(1))
    return urls


def _cursor_in_scope(url):
    path = urllib.parse.urlparse(url).path
    return not any(path.startswith(p) for p in _CURSOR_EXCLUDE_PREFIXES)


def _acquire_cursor_docs():
    rows = []
    llms_txt = _get(_CURSOR_LLMS)
    urls = sorted(set(u for u in _cursor_doc_urls(llms_txt) if _cursor_in_scope(u)))
    n_skip = 0
    for url in urls:
        try:
            body = _get(url)
        except Exception as e:
            print(f"  cursor/docs: {url} SKIPPED ({e})")
            n_skip += 1
            continue
        path_part = urllib.parse.urlparse(url).path
        stem = path_part[:-3] if path_part.endswith(".md") else path_part
        path = _write("cursor", "docs", _slug(stem) + ".md", body)
        rows.append({
            "path": path, "tool": "cursor", "tier": 1, "source": url,
            "date_or_version": None, "chunking": "sectioned",
        })
        time.sleep(0.05)
    print(f"  cursor/docs: {len(rows)} pages ({n_skip} failed fetches, {len(urls)} attempted)")
    return rows


def _acquire_cursor_changelog():
    # Full changelog history needs interactive "load more" pagination (no bulk
    # export exists, confirmed -- see DECISIONS.md). Vendoring only the
    # handful of entries server-rendered on the static page for now.
    changelog_html = _get("https://cursor.com/changelog")
    changelog_text = _html_to_text(changelog_html)
    path = _write("cursor", "changelog", "changelog-recent.md", changelog_text)
    print("  cursor/changelog: recent entries only (full history needs a follow-up decision)")
    return [{
        "path": path, "tool": "cursor", "tier": 2, "source": "https://cursor.com/changelog",
        "date_or_version": None, "chunking": "sectioned",
    }]


def _acquire_cursor_cookbook():
    readme = _get_readme(_CURSOR_COOKBOOK_REPO)
    path = _write("cursor", "cookbook", "plugins-README.md", readme)
    print("  cursor/cookbook: plugins repo README")
    return [{
        "path": path, "tool": "cursor", "tier": 3,
        "source": f"https://github.com/{_CURSOR_COOKBOOK_REPO}",
        "date_or_version": None, "chunking": "sectioned",
    }]


def acquire_cursor():
    return _run_phases("cursor", _acquire_cursor_docs, _acquire_cursor_changelog, _acquire_cursor_cookbook)


# ---------------------------------------------------------------------- codex

_CODEX_MANUAL = "https://learn.chatgpt.com/docs/codex-manual.md"
_CODEX_LLMS_INDEX = "https://learn.chatgpt.com/llms.txt"
_CODEX_REPO = "openai/codex"
_CODEX_COOKBOOK_FILES = ["README.md", "AGENTS.md", "SECURITY.md"]

# Sibling pages of clearly-in-scope Codex categories whose one-line description
# doesn't happen to say "Codex" (spot-checked by hand against the llms.txt
# category they sit in -- see DECISIONS.md).
_CODEX_INCLUDE_OVERRIDES = {
    "https://learn.chatgpt.com/docs/agent-configuration/speed.md",
    "https://learn.chatgpt.com/docs/config-file/config-sample.md",
    "https://learn.chatgpt.com/docs/environments/local-environment.md",
    "https://learn.chatgpt.com/docs/permission-modes.md",
    "https://learn.chatgpt.com/guides/build-ai-native-engineering-team.md",
}


def _codex_llms_index_urls():
    """URLs from the ChatGPT/Codex shared llms.txt whose title+description
    mentions 'Codex' -- the index carries a one-line description per page
    that the manual's per-section body doesn't, so classification happens
    here rather than on the manual's sparser per-section title alone."""
    index = _get(_CODEX_LLMS_INDEX)
    include = set()
    for line in index.splitlines():
        m = re.match(r"\s*-\s*\[(.*?)\]\((\S+?)\):\s*(.*)", line)
        if not m:
            continue
        title, url, desc = m.groups()
        if "codex" in f"{title} {desc}".lower():
            include.add(url)
    return include | _CODEX_INCLUDE_OVERRIDES


def _codex_in_scope(title, url, include_urls):
    return url in include_urls or "codex" in title.lower()


def _split_codex_manual(text):
    """(title, url, body) per '### Title\\n\\nSource: [Title](url)\\n\\n...' section."""
    parts = re.split(r"(?m)^### ", text)
    pages = []
    for part in parts[1:]:
        head, _, rest = part.partition("\n")
        title = head.strip()
        m = re.search(r"^Source: \[.*?\]\((\S+)\)", rest, re.MULTILINE)
        if not m:
            continue
        pages.append((title, m.group(1), rest.strip() + "\n"))
    return pages


def _acquire_codex_docs():
    rows = []
    include_urls = _codex_llms_index_urls()
    manual = _get(_CODEX_MANUAL)
    n_total = 0
    seen_sources = set()
    for title, url, body in _split_codex_manual(manual):
        n_total += 1
        if not _codex_in_scope(title, url, include_urls):
            continue
        if url in seen_sources:
            # the manual can list the same underlying page twice under two
            # topic headings (e.g. "Command line options" and "Slash
            # commands" both citing developer-commands.md?surface=cli) --
            # skip the repeat rather than double-counting its content.
            continue
        seen_sources.add(url)
        parsed = urllib.parse.urlparse(url)
        stem = parsed.path[:-3] if parsed.path.endswith(".md") else parsed.path
        if parsed.query:
            stem += "-" + parsed.query  # e.g. developer-commands.md?surface=cli vs =ide
        path = _write("codex", "docs", _slug(stem) + ".md", body)
        rows.append({
            "path": path, "tool": "codex", "tier": 1, "source": url,
            "date_or_version": None, "chunking": "sectioned",
        })
    print(f"  codex/docs: {len(rows)}/{n_total} sections in scope (filtered out ChatGPT-consumer content)")
    return rows


def _codex_releases_page(page):
    try:
        return json.loads(_get(
            f"https://api.github.com/repos/{_CODEX_REPO}/releases?per_page=100&page={page}"
        ))
    except urllib.error.HTTPError as e:
        if e.code == 422:
            # GitHub caps unauthenticated pagination depth (~1000 results);
            # the tail of very old releases is lost, acceptable for a
            # changelog corpus that cares about recent/stable entries.
            return None
        raise


def _acquire_codex_changelog():
    rows = []
    page = 1
    while releases := _codex_releases_page(page):
        for r in releases:
            if r["prerelease"] or not (r["body"] or "").strip():
                continue
            tag = r["tag_name"]
            body = f"# {tag}\n\nPublished: {r['published_at']}\n\n{r['body']}\n"
            path = _write("codex", "changelog", _slug(tag) + ".md", body)
            rows.append({
                "path": path, "tool": "codex", "tier": 2, "source": r["html_url"],
                "date_or_version": r["published_at"][:10], "chunking": "sectioned",
            })
        page += 1
        time.sleep(0.2)
    print(f"  codex/changelog: {len(rows)} stable releases")
    return rows


def _acquire_codex_cookbook():
    rows = []
    for fname in _CODEX_COOKBOOK_FILES:
        try:
            body = _get(f"https://raw.githubusercontent.com/{_CODEX_REPO}/main/{fname}")
        except Exception as e:
            print(f"  codex/cookbook: {fname} SKIPPED ({e})")
            continue
        path = _write("codex", "cookbook", fname, body)
        rows.append({
            "path": path, "tool": "codex", "tier": 3,
            "source": f"https://github.com/{_CODEX_REPO}/blob/main/{fname}",
            "date_or_version": None, "chunking": "sectioned",
        })
    print(f"  codex/cookbook: {len(rows)} files")
    return rows


def acquire_codex():
    return _run_phases("codex", _acquire_codex_docs, _acquire_codex_changelog, _acquire_codex_cookbook)


def run():
    # Write the manifest incrementally, one tool at a time, so a failure in
    # one tool (e.g. GitHub's unauthenticated rate limit on a same-hour
    # re-run) doesn't discard documents already fetched -- and already
    # written to disk under data/<tool>/... -- for the other two.
    open(MANIFEST_OUT, "w").close()
    rows = []
    for tool, acquire_fn in (
        ("claude_code", acquire_claude_code),
        ("cursor", acquire_cursor),
        ("codex", acquire_codex),
    ):
        print(f"{tool}:")
        try:
            tool_rows = acquire_fn()
        except Exception as e:
            print(f"  {tool}: FAILED ({e}) -- keeping manifest rows already written for other tools")
            continue
        with open(MANIFEST_OUT, "a", encoding="utf-8") as f:
            for row in tool_rows:
                f.write(json.dumps(row, ensure_ascii=False) + "\n")
        rows += tool_rows

    by_tool = {}
    for row in rows:
        by_tool[row["tool"]] = by_tool.get(row["tool"], 0) + 1
    print(f"{len(rows)} documents -> {MANIFEST_OUT}  ({by_tool})")
    return rows
