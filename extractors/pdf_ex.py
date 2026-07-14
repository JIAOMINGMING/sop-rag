"""PDF 解析器：能识别编号章节就按章节切，否则滑窗切分。

定位符始终带页码，这样两种情况下出处都能用。
"""
import fitz

from . import HEADING_NUM_RE, make_chunk, sliding_window


def extract(path):
    pdf = fitz.open(path)
    warnings = []

    # 按阅读顺序的 (页码, 行) 序列
    lines = []
    for page_no, page in enumerate(pdf, start=1):
        for raw in page.get_text().splitlines():
            line = raw.strip()
            if line:
                lines.append((page_no, line))
    pdf.close()

    if not lines:
        return {"chunks": [], "mode": "no-text",
                "warnings": ["未提取到文本（可能是扫描版 PDF，需要 OCR），已跳过"]}

    headings = [i for i, (_, ln) in enumerate(lines)
                if HEADING_NUM_RE.match(ln) and len(ln) < 80]
    doc_title = lines[0][1]

    if len(headings) >= 3:
        chunks = []
        section_path = []                        # [(层级, 标题)]
        bounds = headings + [len(lines)]
        # 第一个标题之前的前言
        pre = [ln for _, ln in lines[:headings[0]] if ln != doc_title]
        if pre:
            chunks.append(make_chunk(path, doc_title,
                                     f"(前言) (p.{lines[0][0]})", None, "\n".join(pre)))
        for h, nxt in zip(headings, bounds[1:]):
            page_start = lines[h][0]
            heading = lines[h][1]
            depth = HEADING_NUM_RE.match(heading).group(1).count(".") + 1
            while section_path and section_path[-1][0] >= depth:
                section_path.pop()
            section_path.append((depth, heading))
            body = "\n".join(ln for _, ln in lines[h + 1:nxt])
            if not body.strip():
                continue
            page_end = lines[nxt - 1][0]
            pages = f"p.{page_start}" if page_start == page_end \
                else f"p.{page_start}-{page_end}"
            breadcrumb = " > ".join(t for _, t in section_path)
            chunks.append(make_chunk(path, doc_title,
                                     f"§{heading} ({pages})", breadcrumb, body))
        return {"chunks": chunks, "mode": "sections", "warnings": warnings}

    # 没有编号结构 → 对全文滑窗切分，同时追踪页码
    offsets, full = [], ""
    for page_no, ln in lines:
        offsets.append((len(full), page_no))
        full += ln + "\n"

    def page_at(pos):
        cur = offsets[0][1]
        for off, pg in offsets:
            if off > pos:
                break
            cur = pg
        return cur

    chunks = []
    for start, seg in sliding_window(full):
        p1, p2 = page_at(start), page_at(start + len(seg) - 1)
        pages = f"p.{p1}" if p1 == p2 else f"p.{p1}-{p2}"
        chunks.append(make_chunk(path, doc_title, pages, None, seg))
    warnings.append("未识别出编号章节，按滑窗切分并标注页码")
    return {"chunks": chunks, "mode": "sliding-window", "warnings": warnings}
