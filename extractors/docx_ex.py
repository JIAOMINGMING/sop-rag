"""Word 解析器：有 Heading 样式就按样式切，没有则用排版启发式识别标题。"""
import re
from pathlib import Path

from docx import Document
from docx.table import Table
from docx.text.paragraph import Paragraph

from . import HEADING_NUM_RE, make_chunk, sliding_window


def iter_body(doc):
    for child in doc.element.body.iterchildren():
        if child.tag.endswith("}p"):
            yield Paragraph(child, doc)
        elif child.tag.endswith("}tbl"):
            yield Table(child, doc)


def table_text(tbl):
    lines = []
    for row in tbl.rows:
        cells = [c.text.strip() for c in row.cells]
        if any(cells):
            lines.append(" | ".join(cells))
    return "\n".join(lines)


def is_bold_para(p):
    runs = [r for r in p.runs if r.text.strip()]
    return bool(runs) and all(r.bold for r in runs)


def heuristic_heading_level(p):
    """无样式文档：返回标题层级，正文则返回 None。"""
    text = p.text.strip()
    if not text or len(text) > 80:
        return None
    m = HEADING_NUM_RE.match(text)
    if m and (is_bold_para(p) or len(text) < 60):
        return m.group(1).count(".") + 1
    if is_bold_para(p) and len(text) < 60 and not text.endswith(("。", ".", "；", ";")):
        return 2
    return None


def extract(path, display_path=None):
    doc = Document(path)
    display_path = display_path or path
    styled = sum(1 for p in doc.paragraphs
                 if p.style and p.style.name.startswith("Heading ") and p.text.strip())
    mode = "styles" if styled >= 3 else "heuristic"

    doc_title, meta_version = "", ""
    chunks, warnings = [], []
    section_path, buf = [], []

    def flush():
        text = "\n".join(t for t in buf if t.strip())
        buf.clear()
        if not text.strip():
            return
        if not section_path:                     # 第一个标题之前的前言
            section_path.append((1, "(前言)"))
        section = section_path[-1][1]
        breadcrumb = " > ".join(h for _, h in section_path)
        c = make_chunk(display_path, doc_title, f"§{section}", breadcrumb, text)
        c["version"] = meta_version
        chunks.append(c)

    def heading_level(p):
        style = p.style.name if p.style else ""
        if mode == "styles":
            if style.startswith("Heading "):
                return int(style.split()[-1])
            return None
        return heuristic_heading_level(p)

    for el in iter_body(doc):
        if isinstance(el, Table):
            txt = table_text(el)
            if not doc_title and "Document No." in txt:
                m = re.search(r"Version \| (.+)", txt)
                meta_version = m.group(1).strip() if m else ""
                continue
            buf.append(txt)
            continue
        text = el.text.strip()
        if not text:
            continue
        style = el.style.name if el.style else ""
        if style == "Title" and not doc_title:
            doc_title = re.sub(rf"^{re.escape(Path(display_path).stem.split('_')[0])}\s+",
                               "", text)
            continue
        lvl = heading_level(el)
        if lvl is not None:
            if not doc_title:
                doc_title = text                  # 第一个标题兼作文档标题
            flush()
            while section_path and section_path[-1][0] >= lvl:
                section_path.pop()
            section_path.append((lvl, text))
        else:
            buf.append(text)
    flush()

    if not chunks:                                # 完全没有文本 → 干净地放弃
        warnings.append("未提取到任何文本")
    elif mode == "heuristic" and len(chunks) == 1:
        mode = "sliding-window"                   # 启发式没找到任何结构
        full = chunks[0]["text"]
        chunks = [make_chunk(display_path, doc_title, f"块{i+1}", None, seg)
                  for i, (_, seg) in enumerate(sliding_window(full))]
        warnings.append("未识别出标题结构，退化为滑窗切分")
    return {"chunks": chunks, "mode": mode, "warnings": warnings}
