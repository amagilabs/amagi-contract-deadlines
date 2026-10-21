"""Turn extracted lines into numbered sections, paragraphs and sentences."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import List, Tuple

from .extract import Document

SECTION_RE = re.compile(
    r"^\s*(?:"
    r"(?:section|article|sec\.|§)\s*(?P<word>\d{1,3}(?:\.\d{1,3})*|[IVXLC]{1,6})\b[.:]?"
    r"|(?P<multi>\d{1,3}(?:\.\d{1,3})+)\.?"
    r"|(?P<single>\d{1,3})[.)]"
    r")\s+(?=\S)",
    re.I,
)
# "Commencement Date: March 1, 2026" style label lines in a basic-terms block.
LABEL_RE = re.compile(r"^\s*[A-Z][A-Za-z'’/&() -]{2,45}:\s+\S")

ABBREVIATIONS = {
    "inc", "ltd", "co", "corp", "llc", "l.l.c", "l.p", "lp", "no", "nos", "sec",
    "secs", "st", "ave", "blvd", "mr", "mrs", "ms", "dr", "u.s", "e.g", "i.e",
    "etc", "jan", "feb", "mar", "apr", "jun", "jul", "aug", "sep", "sept", "oct",
    "nov", "dec", "approx", "para", "p", "pp", "art", "ste", "fl", "vs", "v",
    "ft", "sq", "mo", "yr", "yrs", "esq", "jr", "sr", "n.a", "a.m", "p.m",
}
_SENTENCE_END = re.compile(r"[.!?](?=[\"'”’)]?\s+[\"'“‘(]?[A-Z0-9])")


@dataclass
class Clause:
    """One sentence, with the section it sits in and the paragraph around it."""
    section: str
    page: str
    text: str
    paragraph: str


def _is_heading(text: str) -> bool:
    words = text.split()
    letters = [c for c in text if c.isalpha()]
    return (
        0 < len(words) <= 8
        and bool(letters)
        and sum(c.isupper() for c in letters) / len(letters) > 0.8
        and not text.rstrip().endswith((",", ";"))
    )


def _section_label(match: "re.Match[str]") -> str:
    return match.group("word") or match.group("multi") or match.group("single")


def _paragraphs(doc: Document) -> List[Tuple[str, List[Tuple[int, int]], str]]:
    """(text, [(offset, page)...], section) per paragraph."""
    paragraphs = []
    section = ""
    text, marks = "", []

    def flush():
        nonlocal text, marks
        if text.strip():
            paragraphs.append((text.strip(), marks, section))
        text, marks = "", []

    for line in doc.lines:
        raw = line.text.strip()
        if not raw:
            flush()
            continue
        sec = SECTION_RE.match(raw)
        starts_new = (
            line.hard_break
            or line.heading
            or bool(sec)
            or bool(LABEL_RE.match(raw))
            or _is_heading(raw)
            or (text.rstrip().endswith(":") and not text.rstrip().endswith("as follows:"))
        )
        if starts_new:
            flush()
            if sec:
                section = _section_label(sec)
        if text.endswith("-") and raw[:1].islower():
            text = text[:-1]
        elif text:
            text += " "
        marks.append((len(text), line.page))
        text += raw
        if _is_heading(raw) and not sec:
            flush()
    flush()
    return paragraphs


def _page_at(marks: List[Tuple[int, int]], offset: int) -> int:
    page = marks[0][1] if marks else 1
    for start, number in marks:
        if start > offset:
            break
        page = number
    return page


def split_sentences(text: str) -> List[Tuple[int, int]]:
    """(start, end) spans of the sentences in ``text``."""
    spans, start = [], 0
    for m in _SENTENCE_END.finditer(text):
        before = text[start:m.start()].split()
        last = before[-1].lower().rstrip(".") if before else ""
        last = last.lstrip("(\"'“")
        if last in ABBREVIATIONS or (len(last) == 1 and last.isalpha()):
            continue
        if re.fullmatch(r"\d{1,3}(?:\.\d{1,3})*", last) and len(before) <= 2:
            continue  # "Section 3." at the start of a sentence
        spans.append((start, m.end()))
        start = m.end()
        while start < len(text) and text[start].isspace():
            start += 1
    if start < len(text):
        spans.append((start, len(text)))
    return spans


def clauses(doc: Document) -> List[Clause]:
    out: List[Clause] = []
    for text, marks, section in _paragraphs(doc):
        for start, end in split_sentences(text):
            sentence = text[start:end].strip()
            if not sentence:
                continue
            first, last = _page_at(marks, start), _page_at(marks, max(start, end - 1))
            page = str(first) if first == last else f"{first}-{last}"
            out.append(Clause(section, page, sentence, text))
    return out
