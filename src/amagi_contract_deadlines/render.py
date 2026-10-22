"""Write events as an iCalendar (.ics) file, a CSV and a terminal summary."""

from __future__ import annotations

import csv
import hashlib
import io
import json
from datetime import date, datetime, timedelta, timezone
from typing import Iterable, List, Optional, Sequence

from . import __version__
from .detect import Event, Report

CSV_COLUMNS = [
    "date", "event", "document", "section", "page", "computed", "basis",
    "auto_renews", "clause", "path",
]

DISCLAIMER = (
    "Found by amagi-contract-deadlines from the contract text. Check it against the signed "
    "document before you rely on it. This is not legal advice."
)


def all_events(reports: Iterable[Report]) -> List[Event]:
    events = [ev for report in reports for ev in report.events]
    return sorted(events, key=lambda e: (e.date is None, e.date or date.max, e.document, e.label))


# ---------------------------------------------------------------- CSV

def to_csv(events: Sequence[Event]) -> str:
    buf = io.StringIO()
    writer = csv.writer(buf, lineterminator="\n")
    writer.writerow(CSV_COLUMNS)
    for ev in events:
        writer.writerow([
            ev.date.isoformat() if ev.date else "",
            ev.label,
            ev.document,
            ev.section,
            ev.page,
            "yes" if ev.computed else "no",
            ev.basis,
            "yes" if ev.auto_renews else "no",
            ev.quote,
            ev.path,
        ])
    return buf.getvalue()


# ---------------------------------------------------------------- iCalendar

def _escape(text: str) -> str:
    return (text.replace("\\", "\\\\").replace(";", "\\;").replace(",", "\\,")
            .replace("\r\n", "\\n").replace("\n", "\\n"))


def _fold(line: str) -> str:
    """Fold a content line to 75 octets as RFC 5545 section 3.1 requires."""
    data = line.encode("utf-8")
    if len(data) <= 75:
        return line
    parts, current, size = [], "", 0
    limit = 75
    for ch in line:
        width = len(ch.encode("utf-8"))
        if size + width > limit:
            parts.append(current)
            current, size, limit = "", 0, 74  # continuation lines start with a space
        current += ch
        size += width
    parts.append(current)
    return "\r\n ".join(parts)


def _uid(ev: Event) -> str:
    key = "|".join([ev.path or ev.document, ev.kind, ev.label, ev.date.isoformat(), ev.section])
    return hashlib.sha1(key.encode("utf-8")).hexdigest()[:20] + "@amagi-contract-deadlines"


def describe(ev: Event) -> str:
    where = ev.document
    if ev.section:
        where += f", section {ev.section}"
    if ev.page:
        where += f", page {ev.page}"
    lines = [f"{ev.label} for {ev.document}."]
    if ev.basis:
        lines.append(("How it was worked out: " if ev.computed else "") + ev.basis)
    lines.append(f"Source: {where}")
    lines.append(f"Clause: \"{ev.quote}\"")
    lines.append(DISCLAIMER)
    return "\n".join(lines)


def to_ics(events: Sequence[Event], remind_days: Sequence[int] = (30, 7),
           now: Optional[datetime] = None) -> str:
    now = (now or datetime.now(timezone.utc)).astimezone(timezone.utc)
    stamp = now.strftime("%Y%m%dT%H%M%SZ")
    out = [
        "BEGIN:VCALENDAR",
        "VERSION:2.0",
        f"PRODID:-//AmagiLabs//amagi-contract-deadlines {__version__}//EN",
        "CALSCALE:GREGORIAN",
        "METHOD:PUBLISH",
        "X-WR-CALNAME:Contract deadlines",
    ]
    for ev in events:
        if ev.date is None:
            continue
        summary = f"{ev.label}: {ev.document}"
        out += [
            "BEGIN:VEVENT",
            f"UID:{_uid(ev)}",
            f"DTSTAMP:{stamp}",
            f"DTSTART;VALUE=DATE:{ev.date.strftime('%Y%m%d')}",
            f"DTEND;VALUE=DATE:{(ev.date + timedelta(days=1)).strftime('%Y%m%d')}",
            f"SUMMARY:{_escape(summary)}",
            f"DESCRIPTION:{_escape(describe(ev))}",
            f"CATEGORIES:{_escape(ev.label)}",
            "TRANSP:TRANSPARENT",
        ]
        if ev.is_action:
            for days in remind_days:
                out += [
                    "BEGIN:VALARM",
                    "ACTION:DISPLAY",
                    f"DESCRIPTION:{_escape(f'{days} days to go: {summary}')}",
                    f"TRIGGER:-P{days}D",
                    "END:VALARM",
                ]
        out.append("END:VEVENT")
    out.append("END:VCALENDAR")
    return "\r\n".join(_fold(line) for line in out) + "\r\n"


# ---------------------------------------------------------------- JSON

def to_json(reports: Sequence[Report]) -> str:
    def ev_dict(ev: Event):
        return {
            "date": ev.date.isoformat() if ev.date else None,
            "event": ev.label,
            "kind": ev.kind,
            "document": ev.document,
            "section": ev.section,
            "page": ev.page,
            "computed": ev.computed,
            "basis": ev.basis,
            "auto_renews": ev.auto_renews,
            "clause": ev.quote,
            "path": ev.path,
        }

    return json.dumps({
        "tool": "amagi-contract-deadlines",
        "version": __version__,
        "documents": [
            {
                "path": str(r.path),
                "pages": r.page_count,
                "auto_renews": r.auto_renews,
                "renewal_term": str(r.renewal_term) if r.renewal_term else None,
                "notes": r.notes,
                "relative_notices": r.relative_notices,
                "events": [ev_dict(ev) for ev in r.events],
            }
            for r in reports
        ],
    }, indent=2)


# ---------------------------------------------------------------- terminal

def summary(reports: Sequence[Report], as_of: date) -> str:
    lines: List[str] = []
    width = max([len(ev.label) for r in reports for ev in r.events] + [10])
    for report in reports:
        header = f"{report.path.name} ({report.page_count} page{'s' if report.page_count != 1 else ''})"
        if report.auto_renews:
            header += ", auto-renews"
            if report.renewal_term:
                header += f" for {report.renewal_term}"
        lines.append(header)
        if not report.events:
            lines.append("  no dates found")
        for ev in report.events:
            when = ev.date.isoformat() if ev.date else "no date   "
            where = f"§{ev.section}" if ev.section else ""
            where = f"{where} p.{ev.page}".strip()
            flag = "  computed" if ev.computed else ""
            lines.append(f"  {when}  {ev.label:<{width}} {where}{flag}")
        for note in report.notes:
            lines.append(f"  note: {note}")
        if report.relative_notices:
            n = len(report.relative_notices)
            lines.append(f"  note: {n} notice period{'s' if n != 1 else ''} measured from events with "
                         "no fixed date (assignment, default, etc.); see --json")
    upcoming = [ev for ev in all_events(reports)
                if ev.is_action and ev.date and ev.date >= as_of]
    if upcoming:
        nxt = upcoming[0]
        days = (nxt.date - as_of).days
        lines.append("")
        lines.append(f"Next action: {nxt.label} for {nxt.document} on {nxt.date.isoformat()} "
                     f"({days} day{'s' if days != 1 else ''} from {as_of.isoformat()})")
    return "\n".join(lines)
