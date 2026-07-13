"""Markdown / plain-text extractor: heading-aware for md, numbered lines for txt."""
import re

from . import HEADING_NUM_RE, make_chunk, sliding_window

MD_HEADING_RE = re.compile(r"^(#{1,4})\s+(.+)$")


def extract(path):
    text = path.read_text(encoding="utf-8", errors="replace")
    lines = text.splitlines()

    def heading_of(line):
        m = MD_HEADING_RE.match(line)
        if m:
            return len(m.group(1)), m.group(2).strip()
        m = HEADING_NUM_RE.match(line.strip())
        if m and len(line.strip()) < 80:
            return m.group(1).count(".") + 1, line.strip()
        return None

    headings = [i for i, ln in enumerate(lines) if heading_of(ln)]
    if len(headings) < 2:
        chunks = [make_chunk(path, path.stem, f"块{i+1}", None, seg)
                  for i, (_, seg) in enumerate(sliding_window(text))]
        return {"chunks": chunks, "mode": "sliding-window",
                "warnings": ["未识别出标题结构，滑窗切分"]}

    chunks, section_path = [], []
    doc_title = heading_of(lines[headings[0]])[1]
    bounds = headings + [len(lines)]
    for h, nxt in zip(headings, bounds[1:]):
        lvl, title = heading_of(lines[h])
        while section_path and section_path[-1][0] >= lvl:
            section_path.pop()
        section_path.append((lvl, title))
        body = "\n".join(lines[h + 1:nxt]).strip()
        if not body:
            continue
        breadcrumb = " > ".join(t for _, t in section_path)
        chunks.append(make_chunk(path, doc_title, f"§{title}", breadcrumb, body))
    return {"chunks": chunks, "mode": "sections", "warnings": []}
