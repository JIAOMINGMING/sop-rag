#!/usr/bin/env python3
"""入库：docs/*（docx/doc/pdf/xlsx/md/txt）→ 统一 chunk → OpenAI 向量。

增量：内容 hash 未变的文件直接复用缓存向量。
每份文件打印一份解析质量报告，脏文件不会静默失败。
"""
import hashlib
import json
import re
from pathlib import Path

import numpy as np
import requests

from extractors import SUPPORTED, extract

ROOT = Path(__file__).parent
DOCS = ROOT / "docs"
INDEX = ROOT / "index"
EMBED_MODEL = "text-embedding-3-small"
EMBED_BATCH = 100
KEY_FILE = Path.home() / "learning-plan/coach/config.sh"


def get_api_key():
    import os
    if os.environ.get("OPENAI_API_KEY"):
        return os.environ["OPENAI_API_KEY"]
    env_file = ROOT / ".env"
    if env_file.exists():
        m = re.search(r'^(?:export )?OPENAI_API_KEY="?([^"\n]+)"?',
                      env_file.read_text(), re.M)
        if m:
            return m.group(1)
    if KEY_FILE.exists():
        m = re.search(r'^export OPENAI_API_KEY="?([^"\n]+)"?', KEY_FILE.read_text(), re.M)
        if m:
            return m.group(1)
    raise SystemExit("OPENAI_API_KEY not found: set the env var, or put "
                     "OPENAI_API_KEY=sk-... in a .env file next to ingest.py")


def embed(texts, api_key):
    vecs = []
    for i in range(0, len(texts), EMBED_BATCH):
        r = requests.post(
            "https://api.openai.com/v1/embeddings",
            headers={"Authorization": f"Bearer {api_key}"},
            json={"model": EMBED_MODEL, "input": texts[i:i + EMBED_BATCH]},
            timeout=120,
        )
        r.raise_for_status()
        data = sorted(r.json()["data"], key=lambda d: d["index"])
        vecs.extend(d["embedding"] for d in data)
    return np.array(vecs, dtype=np.float32)


def file_hash(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def embed_input(c):
    return f"[{c['doc_no']} {c['doc_title']}] {c['breadcrumb']}\n{c['text']}"


def load_previous():
    """返回上次运行的 (manifest, 按doc_id分组的chunks, 按doc_id分组的向量)。"""
    manifest_f, chunks_f, vecs_f = (INDEX / "manifest.json",
                                    INDEX / "chunks.json", INDEX / "embeddings.npy")
    if not (manifest_f.exists() and chunks_f.exists() and vecs_f.exists()):
        return {}, {}, {}
    manifest = json.loads(manifest_f.read_text(encoding="utf-8"))
    chunks = json.loads(chunks_f.read_text(encoding="utf-8"))
    vecs = np.load(vecs_f)
    if len(chunks) != len(vecs) or (chunks and "doc_id" not in chunks[0]):
        return {}, {}, {}                        # 索引过期/旧版格式 → 整体重建
    by_doc_c, by_doc_v = {}, {}
    for c, v in zip(chunks, vecs):
        by_doc_c.setdefault(c["doc_id"], []).append(c)
        by_doc_v.setdefault(c["doc_id"], []).append(v)
    return manifest, by_doc_c, by_doc_v


def main():
    files = sorted(p for p in DOCS.iterdir()
                   if p.is_file() and not p.name.startswith("~$")
                   and p.suffix.lower() in SUPPORTED)
    skipped = sorted(p.name for p in DOCS.iterdir()
                     if p.is_file() and not p.name.startswith("~$")
                     and p.suffix.lower() not in SUPPORTED)

    old_manifest, old_chunks, old_vecs = load_previous()
    manifest, report = {}, []
    all_chunks, all_vecs, new_chunks = [], [], []

    for path in files:
        h = file_hash(path)
        manifest[path.name] = h
        if old_manifest.get(path.name) == h and path.name in old_chunks:
            all_chunks.extend(old_chunks[path.name])
            all_vecs.extend(old_vecs[path.name])
            report.append((path.name, "cached", len(old_chunks[path.name]), []))
            continue
        try:
            result = extract(path)
        except Exception as e:                    # 单个坏文件不能中断整轮
            report.append((path.name, "FAILED", 0, [f"{type(e).__name__}: {e}"]))
            continue
        chunks = result["chunks"]
        report.append((path.name, result["mode"], len(chunks), result["warnings"]))
        for c in chunks:
            all_chunks.append(c)
            all_vecs.append(None)                 # 占位，向量化后回填
            new_chunks.append((len(all_chunks) - 1, c))

    if new_chunks:
        api_key = get_api_key()
        vecs = embed([embed_input(c) for _, c in new_chunks], api_key)
        vecs /= np.linalg.norm(vecs, axis=1, keepdims=True)
        for (pos, _), v in zip(new_chunks, vecs):
            all_vecs[pos] = v

    INDEX.mkdir(exist_ok=True)
    (INDEX / "chunks.json").write_text(
        json.dumps(all_chunks, ensure_ascii=False, indent=1), encoding="utf-8")
    np.save(INDEX / "embeddings.npy",
            np.array(all_vecs, dtype=np.float32) if all_vecs
            else np.zeros((0, 1536), dtype=np.float32))
    (INDEX / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=1), encoding="utf-8")

    print(f"\n{'文件':<42} {'解析方式':<16} chunks")
    print("-" * 68)
    for name, mode, n, warns in report:
        print(f"{name:<42} {mode:<16} {n}")
        for w in warns:
            print(f"    ⚠ {w}")
    for name in skipped:
        print(f"{name:<42} {'不支持的格式':<16} -")
    n_new = len(new_chunks)
    print(f"\n共 {len(all_chunks)} chunks（新向量化 {n_new}，缓存复用 "
          f"{len(all_chunks) - n_new}）-> index/")


if __name__ == "__main__":
    main()
