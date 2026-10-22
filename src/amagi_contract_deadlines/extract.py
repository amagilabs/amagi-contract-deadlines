"""Pull text out of PDF, DOCX and plain-text contracts, page by page."""

from __future__ import annotations

import unicodedata
from dataclasses import dataclass, field
from pathlib import Path
from typing import List


class ExtractError(Exception):
    """The file could not be read as a contract."""


class NoTextError(ExtractError):
    """The file has no extractable text (usually a scanned PDF)."""


@dataclass
class RawLine:
    text: str
    page: int
    # True when the source marks this line as its own paragraph (DOCX
    # paragraphs, table rows). PDF lines are soft-wrapped and get False.
    hard_break: bool = False
    # True when the source styles this line as a heading (DOCX "Heading N").
    heading: bool = False


@dataclass
class Document:
    path: Path
    kind: str  # "pdf", "docx" or "text"
    page_count: int
    # PDF page numbers are exact. DOCX pages come from page-break markers
    # Word saved in the file, so they are an estimate.
    pages_exact: bool
    lines: List[RawLine] = field(default_factory=list)


def clean(text: str) -> str:
    text = unicodedata.normalize("NFKC", text)
    text = text.replace(" ", " ").replace("\t", "  ")
    return text.rstrip()


def load(path: Path) -> Document:
    path = Path(path)
    if not path.exists():
        raise ExtractError(f"file not found: {path}")
    suffix = path.suffix.lower()
    if suffix == ".pdf":
        doc = _load_pdf(path)
    elif suffix == ".docx":
        doc = _load_docx(path)
    elif suffix in (".txt", ".md", ".text"):
        doc = _load_text(path)
    else:
        raise ExtractError(f"unsupported file type '{suffix}' (use .pdf, .docx or .txt)")
    if not any(line.text.strip() for line in doc.lines):
        if doc.kind == "pdf":
            raise NoTextError(
                f"{path.name} has no text layer (scanned image?). OCR it first, "
                "for example: ocrmypdf input.pdf output.pdf"
            )
        raise NoTextError(f"{path.name} contains no text")
    return doc


def _load_pdf(path: Path) -> Document:
    from pypdf import PdfReader
    from pypdf.errors import PdfReadError

    try:
        reader = PdfReader(str(path))
        if reader.is_encrypted:
            reader.decrypt("")
        pages = list(reader.pages)
    except (PdfReadError, ValueError, OSError) as exc:
        raise ExtractError(f"could not read PDF {path.name}: {exc}") from exc

    lines: List[RawLine] = []
    for number, page in enumerate(pages, start=1):
        try:
            text = page.extract_text() or ""
        except Exception as exc:  # pypdf raises a wide range on damaged pages
            raise ExtractError(f"could not extract text from page {number}: {exc}") from exc
        for line in text.splitlines():
            lines.append(RawLine(clean(line), number))
    return Document(path, "pdf", len(pages), True, lines)


def _load_text(path: Path) -> Document:
    text = path.read_text(encoding="utf-8", errors="replace")
    chunks = text.split("\f")
    lines = [
        RawLine(clean(line), number)
        for number, chunk in enumerate(chunks, start=1)
        for line in chunk.splitlines()
    ]
    return Document(path, "text", len(chunks), len(chunks) > 1, lines)


def _load_docx(path: Path) -> Document:
    import zipfile

    from docx import Document as open_docx
    from docx.oxml.ns import qn
    from docx.text.paragraph import Paragraph

    try:
        docx = open_docx(str(path))
    except (zipfile.BadZipFile, KeyError, ValueError) as exc:
        raise ExtractError(f"could not read DOCX {path.name}: {exc}") from exc

    body = docx.element.body
    # Word writes lastRenderedPageBreak wherever a page actually ended the
    # last time it laid out the document. When those markers exist they are
    # the best page signal; otherwise fall back to hard page breaks.
    rendered = any(True for _ in body.iter(qn("w:lastRenderedPageBreak")))

    T, TAB, BR, CR = qn("w:t"), qn("w:tab"), qn("w:br"), qn("w:cr")
    LRPB, PPR, PBB = qn("w:lastRenderedPageBreak"), qn("w:pPr"), qn("w:pageBreakBefore")
    TYPE = qn("w:type")

    lines: List[RawLine] = []
    page = 1

    def is_break(el) -> bool:
        if rendered:
            return el.tag == LRPB
        return el.tag == BR and el.get(TYPE) == "page"

    def walk_paragraph(p_el, heading: bool) -> None:
        nonlocal page
        ppr = p_el.find(PPR)
        if not rendered and ppr is not None and ppr.find(PBB) is not None and lines:
            page += 1
        parts: List[str] = []
        first = True  # text after a mid-paragraph page break continues the paragraph
        for el in p_el.iter():
            if is_break(el):
                text = clean("".join(parts))
                if text.strip():
                    lines.append(RawLine(text, page, first, heading))
                    first = False
                parts = []
                page += 1
            elif el.tag == T:
                parts.append(el.text or "")
            elif el.tag == TAB:
                parts.append("  ")
            elif el.tag in (BR, CR):
                parts.append(" ")
        text = clean("".join(parts))
        if text.strip():
            lines.append(RawLine(text, page, first, heading))

    for child in body.iterchildren():
        if child.tag == qn("w:p"):
            style = ""
            try:
                style = Paragraph(child, docx).style.name or ""
            except (AttributeError, KeyError):
                pass
            walk_paragraph(child, style.lower().startswith(("heading", "title")))
        elif child.tag == qn("w:tbl"):
            for row in child.iter(qn("w:tr")):
                breaks = sum(1 for el in row.iter() if is_break(el))
                cells: List[str] = []
                for cell in row.iter(qn("w:tc")):
                    text = " ".join(
                        clean("".join(t.text or "" for t in p.iter(T)))
                        for p in cell.iter(qn("w:p"))
                    ).strip()
                    if text and (not cells or cells[-1] != text):
                        cells.append(text)
                page += breaks
                if cells:
                    lines.append(RawLine("  ".join(cells), page, True, False))

    return Document(path, "docx", page, False, lines)
