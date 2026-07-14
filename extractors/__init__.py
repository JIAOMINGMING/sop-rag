"""按格式自适应的文档解析器。

每个解析器都返回相同结构的结果：
    {
      "chunks": [{doc_id, doc_no, doc_title, locator, breadcrumb, text}, ...],
      "mode":   文件的解析方式（"styles" / "heuristic" / "sections" /
                "sliding-window" / "sheet-rows" / ...）,
      "warnings": [str, ...],
    }
这样检索和作答层完全不需要知道源文件的格式。
"""
import re
import shutil
import subprocess
import tempfile
from pathlib import Path

HEADING_NUM_RE = re.compile(r"^(\d+(?:\.\d+)*)[\.\s]\s*\S")

SUPPORTED = {".docx", ".doc", ".pdf", ".xlsx", ".xlsm", ".md", ".txt"}


def doc_no_of(path):
    """`SOP-QC-010_OOS调查.docx` → `SOP-QC-010`；无下划线的文件名原样保留。"""
    return Path(path).stem.split("_")[0]


def make_chunk(path, doc_title, locator, breadcrumb, text):
    return {
        "doc_id": Path(path).name,
        "doc_no": doc_no_of(path),
        "doc_title": doc_title or Path(path).stem,
        "locator": locator,
        "breadcrumb": breadcrumb or locator,
        "text": text.strip(),
    }


def sliding_window(text, size=1200, overlap=200):
    """识别不出结构时的兜底切分。"""
    out, start = [], 0
    while start < len(text):
        end = min(start + size, len(text))
        if end < len(text):                       # 尽量在换行处断开
            nl = text.rfind("\n", start + size // 2, end)
            if nl > start:
                end = nl
        out.append((start, text[start:end]))
        if end >= len(text):
            break
        start = max(end - overlap, start + 1)
    return out


def convert_doc_to_docx(path):
    """老 .doc → 经 LibreOffice 转成临时 .docx；不可用时返回 None。"""
    soffice = shutil.which("soffice") or shutil.which("libreoffice")
    if not soffice:
        return None
    tmp = Path(tempfile.mkdtemp(prefix="sop-rag-doc-"))
    r = subprocess.run([soffice, "--headless", "--convert-to", "docx",
                        "--outdir", str(tmp), str(path)],
                       capture_output=True, timeout=120)
    out = tmp / (Path(path).stem + ".docx")
    return out if r.returncode == 0 and out.exists() else None


def extract(path):
    """按扩展名分发。遇到不支持的类型抛 ValueError。"""
    from . import docx_ex, pdf_ex, xlsx_ex, text_ex
    path = Path(path)
    suffix = path.suffix.lower()
    if suffix == ".docx":
        return docx_ex.extract(path)
    if suffix == ".doc":
        converted = convert_doc_to_docx(path)
        if converted is None:
            return {"chunks": [], "mode": "unsupported",
                    "warnings": [".doc 需要 LibreOffice 转换，未检测到 soffice，已跳过"]}
        result = docx_ex.extract(converted, display_path=path)
        result["warnings"].append("已通过 LibreOffice 从 .doc 转换")
        return result
    if suffix == ".pdf":
        return pdf_ex.extract(path)
    if suffix in (".xlsx", ".xlsm"):
        return xlsx_ex.extract(path)
    if suffix in (".md", ".txt"):
        return text_ex.extract(path)
    raise ValueError(f"不支持的文件类型: {path.name}")
