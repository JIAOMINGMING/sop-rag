#!/usr/bin/env python3
"""Ask a question across all documents: retrieve top-k chunks, answer with citations.

Usage: .venv/bin/python ask.py "偏差的初步评估要在几天内完成？"
       .venv/bin/python ask.py --show-hits "..."   # also print retrieved chunks
"""
import json
import re
import subprocess
import sys
from pathlib import Path

import numpy as np

from ingest import embed, get_api_key

ROOT = Path(__file__).parent
INDEX = ROOT / "index"
DOCS = ROOT / "docs"
TOP_K = 6

PROMPT_TEMPLATE = """你是制药公司质量与药物警戒部门的文档检索助手。请只依据下面提供的文档片段回答问题，禁止使用片段之外的知识编造内容。

回答要求：
1. 用中文回答，直接给出结论和关键数字/时限。
2. 每个论点后面用【文档编号 定位】标注出处，定位原样照抄片段头部方括号里的内容，例如【SOP-QA-001 §5.2.1 Timeline】、【SOP-TR-011 §4.2 Annual Refresher (p.2)】、【QA-LOG-2026 Sheet「偏差台账」行15-30】。
3. 如果答案涉及多份文档，分别说明并都给出出处。
4. 如果提供的片段不足以回答，明确说"现有文档片段中未找到答案"，不要猜。
5. 最后加一行"来源:"列出所有引用的 文档编号+定位。

=== 文档片段 ===
{context}

=== 问题 ===
{question}"""


def retrieve(question, top_k=TOP_K):
    chunks = json.loads((INDEX / "chunks.json").read_text(encoding="utf-8"))
    vecs = np.load(INDEX / "embeddings.npy")
    q = embed([question], get_api_key())[0]
    q /= np.linalg.norm(q)
    scores = vecs @ q
    order = np.argsort(-scores)[:top_k]
    return [(float(scores[i]), chunks[i]) for i in order]


def build_context(hits):
    parts = []
    for score, c in hits:
        ver = f" v{c['version']}" if c.get("version") else ""
        parts.append(f"--- [{c['doc_no']}{ver} {c['doc_title']} {c['locator']}] "
                     f"(相关度 {score:.3f})\n{c['text']}")
    return "\n\n".join(parts)


def answer(question, hits):
    prompt = PROMPT_TEMPLATE.format(context=build_context(hits), question=question)
    r = subprocess.run(["claude", "-p"], input=prompt, capture_output=True,
                       text=True, timeout=300)
    if r.returncode != 0:
        raise SystemExit(f"claude CLI failed: {r.stderr.strip()}")
    return r.stdout.strip()


def source_links(answer_text, hits):
    """Map each 【doc_no …】 citation in the answer to a clickable file:// link.

    PDF links get #page=N (from the citation's "p.N", falling back to the
    first retrieved chunk of that document). One link per unique target.
    """
    doc_of = {}
    for _, c in hits:
        doc_of.setdefault(c["doc_no"], c)
    links, seen = [], set()
    for m in re.finditer(r"【(\S+)([^】]*)】", answer_text):
        c = doc_of.get(m.group(1))
        if c is None:
            continue
        path = DOCS / c["doc_id"]
        if not path.exists():
            continue
        uri = path.as_uri()
        if path.suffix.lower() == ".pdf":
            pm = re.search(r"p\.(\d+)", m.group(2)) or re.search(r"p\.(\d+)", c["locator"])
            if pm:
                uri += f"#page={pm.group(1)}"
        if uri not in seen:
            seen.add(uri)
            links.append(f"  {c['doc_no']}  {uri}")
    return links


def main():
    args = sys.argv[1:]
    show_hits = "--show-hits" in args
    args = [a for a in args if a != "--show-hits"]
    if not args:
        raise SystemExit(__doc__)
    question = args[0]

    hits = retrieve(question)
    if show_hits:
        print("=== 检索命中 ===")
        for score, c in hits:
            print(f"  {score:.3f}  {c['doc_no']} {c['locator']}")
        print()
    text = answer(question, hits)
    print(text)
    links = source_links(text, hits)
    if links:
        print("\n📎 原文链接:")
        print("\n".join(links))


if __name__ == "__main__":
    main()
