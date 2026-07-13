"""Format-adaptive document extractors.

Every extractor returns the same result shape:
    {
      "chunks": [{doc_id, doc_no, doc_title, locator, breadcrumb, text}, ...],
      "mode":   how the file was parsed ("styles" / "heuristic" / "sections" /
                "sliding-window" / "sheet-rows" / ...),
      "warnings": [str, ...],
    }
so retrieval and answering never need to know the source format.
"""
import re
import shutil
import subprocess
import tempfile
from pathlib import Path

HEADING_NUM_RE = re.compile(r"^(\d+(?:\.\d+)*)[\.\s]\s*\S")

SUPPORTED = {".docx", ".doc", ".pdf", ".xlsx", ".xlsm", ".md", ".txt"}


def doc_no_of(path):
    """`SOP-QC-010_OOS调查.docx` -> `SOP-QC-010`; plain stems stay as-is."""
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
    """Fallback chunking when no structure is detectable."""
    out, start = [], 0
    while start < len(text):
        end = min(start + size, len(text))
        if end < len(text):                       # try to break at a newline
            nl = text.rfind("\n", start + size // 2, end)
            if nl > start:
                end = nl
        out.append((start, text[start:end]))
        if end >= len(text):
            break
        start = max(end - overlap, start + 1)
    return out


def convert_doc_to_docx(path):
    """Legacy .doc -> temp .docx via LibreOffice; None if unavailable."""
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
    """Dispatch by extension. Raises ValueError for unsupported types."""
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
    raise ValueError(f"unsupported file type: {path.name}")
