from datetime import date
from pathlib import Path

import pytest

from minipdf import write_pdf

from amagi_deadlines.detect import analyze
from amagi_deadlines.extract import load

EXAMPLES = Path(__file__).resolve().parents[1] / "examples"
AS_OF = date(2026, 10, 21)


@pytest.fixture
def examples() -> Path:
    return EXAMPLES


@pytest.fixture
def make_pdf(tmp_path):
    """make_pdf([[page 1 lines], [page 2 lines]]) -> path to a real PDF."""
    def _make(pages, name="doc.pdf"):
        return write_pdf(tmp_path / name, pages)
    return _make


@pytest.fixture
def make_txt(tmp_path):
    """make_txt("text") -> path; use \f to separate pages."""
    def _make(text, name="doc.txt"):
        path = tmp_path / name
        path.write_text(text, encoding="utf-8")
        return path
    return _make


@pytest.fixture
def run(make_txt):
    """run("contract text") -> Report, analyzed as of 2026-10-21."""
    def _run(text, as_of=AS_OF):
        return analyze(load(make_txt(text)), as_of=as_of)
    return _run


def dated(report):
    """{label: iso date} for every dated event."""
    return {ev.label: ev.date.isoformat() for ev in report.events if ev.date}
