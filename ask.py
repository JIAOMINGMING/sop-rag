#!/usr/bin/env python3
"""跨全部文档提问：检索 top-k 片段，基于命中片段作答并标注出处。

用法: .venv/bin/python ask.py "偏差的初步评估要在几天内完成？"
      .venv/bin/python ask.py --show-hits "..."   # 同时打印检索命中的片段
"""
import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

import numpy as np
import requests

from ingest import embed, get_api_key

ROOT = Path(__file__).parent
INDEX = ROOT / "index"
DOCS = ROOT / "docs"
TOP_K = 6
CHAT_MODEL = os.environ.get("SOP_RAG_CHAT_MODEL", "gpt-4o-mini")

PROMPT_TEMPLATE = """你是制药公司质量与药物警戒部门的文档检索助手。请只依据下面提供的文档片段回答问题，禁止使用片段之外的知识编造内容。

回答要求：
1. 用与问题相同的语言回答（中文问题用中文，英文问题用英文，日文问题用日文），直接给出结论和关键数字/时限。
2. 每个论点后面用【文档编号 定位】标注出处，定位原样照抄片段头部方括号里的内容，例如【SOP-QA-001 §5.2.1 Timeline】、【SOP-TR-011 §4.2 Annual Refresher (p.2)】、【QA-LOG-2026 Sheet「偏差台账」行15-30】。
3. 如果答案涉及多份文档，分别说明并都给出出处。
4. 如果提供的片段不足以回答，明确说明未找到答案（中文"现有文档片段中未找到答案"，英文"Not found in the provided documents"，日文「提供された文書には該当する記載がありません」），不要猜。
5. 最后加一行来源清单（中文"来源:"，英文"Sources:"，日文「出典:」）列出所有引用的 文档编号+定位。

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


def answer_openai(prompt, api_key):
    r = requests.post(
        "https://api.openai.com/v1/chat/completions",
        headers={"Authorization": f"Bearer {api_key}"},
        json={"model": CHAT_MODEL, "temperature": 0.2,
              "messages": [{"role": "user", "content": prompt}]},
        timeout=120,
    )
    r.raise_for_status()
    return r.json()["choices"][0]["message"]["content"].strip()


def answer_claude(prompt):
    r = subprocess.run(["claude", "-p"], input=prompt, capture_output=True,
                       text=True, timeout=300)
    if r.returncode != 0:
        raise RuntimeError(f"claude CLI failed: {r.stderr.strip()}")
    return r.stdout.strip()


def question_lang(q):
    """按提问文字判断作答语言：含假名→ja，含中日文汉字→zh，否则→en。

    仅用于强制作答语言与提问一致（整段 prompt 是中文，模型默认会跟着用中文答）。
    """
    for ch in q:
        if "぀" <= ch <= "ゟ" or "゠" <= ch <= "ヿ":   # 平假名 / 片假名 → 日文
            return "ja"
    if any("一" <= ch <= "鿿" for ch in q):            # 汉字（无假名）→ 中文
        return "zh"
    return "en"


def answer(question, hits):
    """用配置的 LLM 后端作答。

    SOP_RAG_LLM=openai|claude 可强制指定后端；默认 "auto" 优先用 OpenAI API
    （和向量化共用同一个 key，无需 Claude 订阅），没有 key 时回退到 claude 命令行。
    """
    prompt = PROMPT_TEMPLATE.format(context=build_context(hits), question=question)
    # 明确指令作答语言，避免非中文问题被中文 prompt 带成中文回答
    lang = question_lang(question)
    if lang == "en":
        prompt += ('\n\n[IMPORTANT] The question is in English — write the ENTIRE '
                   'answer in English, including the final "Sources:" line. Keep the '
                   '【doc_no locator】 citation markers exactly as they appear.')
    elif lang == "ja":
        prompt += ("\n\n【重要】質問は日本語です——回答全体を日本語で書いてください"
                   "（最後の「出典:」の行も含めて）。【doc_no locator】の引用マーカー"
                   "はそのまま残してください。")
    else:
        prompt += "\n\n【重要】问题是中文——整段回答必须用中文。"
    backend = os.environ.get("SOP_RAG_LLM", "auto")
    if backend == "claude":
        return answer_claude(prompt)
    if backend == "openai":
        return answer_openai(prompt, get_api_key())
    try:
        key = get_api_key()
    except SystemExit:
        key = None
    if key:
        return answer_openai(prompt, key)
    if shutil.which("claude"):
        return answer_claude(prompt)
    raise SystemExit("No answering backend: set OPENAI_API_KEY (or .env) "
                     "or install the claude CLI")


def cited_sources(answer_text, hits):
    """为每个【文档编号 …】出处返回去重后的 (doc_no, doc_id, 页码或None)。

    页码取自出处里的 "p.N"（取不到则回退到该文档第一个命中片段），且只对 PDF 设置。
    """
    doc_of = {}
    for _, c in hits:
        doc_of.setdefault(c["doc_no"], c)
    out, seen = [], set()
    for m in re.finditer(r"【(\S+)([^】]*)】", answer_text):
        c = doc_of.get(m.group(1))
        if c is None:
            continue
        path = DOCS / c["doc_id"]
        if not path.exists():
            continue
        page = None
        if path.suffix.lower() == ".pdf":
            pm = re.search(r"p\.(\d+)", m.group(2)) or re.search(r"p\.(\d+)", c["locator"])
            if pm:
                page = int(pm.group(1))
        key = (c["doc_id"], page)
        if key not in seen:
            seen.add(key)
            out.append((c["doc_no"], c["doc_id"], page))
    return out


def source_links(answer_text, hits):
    """终端版：可点击的 file:// 链接（PDF 带 #page=N）。"""
    links = []
    for doc_no, doc_id, page in cited_sources(answer_text, hits):
        uri = (DOCS / doc_id).as_uri()
        if page:
            uri += f"#page={page}"
        links.append(f"  {doc_no}  {uri}")
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
