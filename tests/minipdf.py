"""Write simple text-only PDFs with no third-party dependencies.

Used to build test fixtures: each page is a list of text lines set in
Helvetica, one line per row, top to bottom. Good enough for pypdf to extract
the same lines back out, which is all the tests need.
"""

from __future__ import annotations

from pathlib import Path
from typing import List, Sequence


def _escape(text: str) -> str:
    return text.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")


def _content_stream(lines: Sequence[str], font_size: int = 10) -> bytes:
    leading = font_size + 4
    ops: List[str] = ["BT", f"/F1 {font_size} Tf", f"{leading} TL", "72 740 Td"]
    for line in lines:
        ops.append(f"({_escape(line)}) Tj")
        ops.append("T*")
    ops.append("ET")
    return "\n".join(ops).encode("cp1252")


def write_pdf(path: Path, pages: Sequence[Sequence[str]]) -> Path:
    """Write ``pages`` (a list of pages, each a list of lines) to ``path``."""
    objects: List[bytes] = []

    def add(obj: bytes) -> int:
        objects.append(obj)
        return len(objects)

    catalog_id = add(b"")  # placeholder, filled below
    pages_id = add(b"")
    font_id = add(b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica /Encoding /WinAnsiEncoding >>")

    page_ids: List[int] = []
    for lines in pages:
        stream = _content_stream(lines)
        content_id = add(b"<< /Length %d >>\nstream\n" % len(stream) + stream + b"\nendstream")
        page_id = add(
            (
                f"<< /Type /Page /Parent {pages_id} 0 R /MediaBox [0 0 612 792] "
                f"/Resources << /Font << /F1 {font_id} 0 R >> >> /Contents {content_id} 0 R >>"
            ).encode("ascii")
        )
        page_ids.append(page_id)

    kids = " ".join(f"{pid} 0 R" for pid in page_ids)
    objects[pages_id - 1] = f"<< /Type /Pages /Kids [{kids}] /Count {len(page_ids)} >>".encode("ascii")
    objects[catalog_id - 1] = f"<< /Type /Catalog /Pages {pages_id} 0 R >>".encode("ascii")

    out = bytearray(b"%PDF-1.4\n")
    offsets: List[int] = []
    for number, body in enumerate(objects, start=1):
        offsets.append(len(out))
        out += f"{number} 0 obj\n".encode("ascii") + body + b"\nendobj\n"
    xref_at = len(out)
    out += f"xref\n0 {len(objects) + 1}\n".encode("ascii")
    out += b"0000000000 65535 f \n"
    for offset in offsets:
        out += f"{offset:010d} 00000 n \n".encode("ascii")
    out += (
        f"trailer\n<< /Size {len(objects) + 1} /Root {catalog_id} 0 R >>\n"
        f"startxref\n{xref_at}\n%%EOF\n"
    ).encode("ascii")

    path = Path(path)
    path.write_bytes(bytes(out))
    return path
