# -*- coding: utf-8 -*-
"""简历文本提取：支持 PDF / DOCX / TXT / MD。

统一输出纯文本，后续交给 LLM 或规则引擎结构化。
"""
from pathlib import Path

SUPPORTED = {".pdf", ".docx", ".txt", ".md"}


class UnsupportedFormatError(ValueError):
    pass


def extract_text(path: str | Path) -> str:
    """按扩展名提取文本。"""
    p = Path(path)
    if p.suffix.lower() == ".pdf":
        return _extract_pdf(p)
    if p.suffix.lower() == ".docx":
        return _extract_docx(p)
    if p.suffix.lower() in (".txt", ".md"):
        return p.read_text(encoding="utf-8", errors="replace")
    raise UnsupportedFormatError(
        f"不支持的文件格式 {p.suffix}，请用 PDF / DOCX / TXT / MD")


def _extract_pdf(p: Path) -> str:
    import pdfplumber
    parts = []
    with pdfplumber.open(p) as pdf:
        for page in pdf.pages:
            text = page.extract_text() or ""
            parts.append(text)
    return "\n".join(parts).strip()


def _extract_docx(p: Path) -> str:
    import docx
    doc = docx.Document(str(p))
    parts = [para.text for para in doc.paragraphs if para.text.strip()]
    for table in doc.tables:
        for row in table.rows:
            cells = [c.text.strip() for c in row.cells if c.text.strip()]
            if cells:
                parts.append(" | ".join(cells))
    return "\n".join(parts).strip()