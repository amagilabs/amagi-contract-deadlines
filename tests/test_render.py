import csv
import io
import re
from datetime import date, datetime, timezone

from amagi_deadlines.detect import DEADLINE, EXPIRATION, Event, Report
from amagi_deadlines.render import CSV_COLUMNS, _fold, summary, to_csv, to_ics

NOW = datetime(2026, 10, 21, 12, 0, tzinfo=timezone.utc)


def ev(kind=DEADLINE, when=date(2027, 1, 15), label="Deadline", quote="Pay rent; on time, always."):
    return Event(kind, label, when, "lease.pdf", "5", "2", quote, basis="", path="/x/lease.pdf")


def test_ics_structure_and_reminders():
    text = to_ics([ev(), ev(EXPIRATION, date(2027, 12, 31), "Term ends")], (30, 7), now=NOW)
    assert text.startswith("BEGIN:VCALENDAR\r\n") and text.endswith("END:VCALENDAR\r\n")
    assert "\n" not in text.replace("\r\n", "")
    assert text.count("BEGIN:VEVENT") == 2
    assert "DTSTART;VALUE=DATE:20270115" in text and "DTEND;VALUE=DATE:20270116" in text
    # only the action item gets alarms
    assert text.count("BEGIN:VALARM") == 2
    assert "TRIGGER:-P30D" in text and "TRIGGER:-P7D" in text
    assert "DTSTAMP:20261021T120000Z" in text


def test_ics_escapes_and_folds():
    text = to_ics([ev(quote="x" * 200 + "; a, b")], (), now=NOW)
    for line in text.split("\r\n"):
        assert len(line.encode("utf-8")) <= 75
    unfolded = text.replace("\r\n ", "")
    assert "a\\, b" in unfolded and "\\; a" in unfolded
    assert "BEGIN:VALARM" not in text


def test_fold_does_not_split_multibyte_characters():
    line = "DESCRIPTION:" + "§é" * 60
    for part in _fold(line).split("\r\n"):
        assert len(part.encode("utf-8")) <= 75
    assert _fold(line).replace("\r\n ", "") == line


def test_undated_events_are_left_out_of_the_calendar():
    text = to_ics([ev(when=None)], (30,), now=NOW)
    assert "BEGIN:VEVENT" not in text


def test_uids_are_stable():
    later = datetime(2030, 1, 1, tzinfo=timezone.utc)
    a = re.search(r"UID:(\S+)", to_ics([ev()], (), now=NOW)).group(1)
    b = re.search(r"UID:(\S+)", to_ics([ev()], (), now=later)).group(1)
    assert a == b


def test_csv_columns_and_rows():
    rows = list(csv.reader(io.StringIO(to_csv([ev(), ev(when=None)]))))
    assert rows[0] == CSV_COLUMNS
    assert rows[1][:5] == ["2027-01-15", "Deadline", "lease.pdf", "5", "2"]
    assert rows[1][CSV_COLUMNS.index("clause")] == "Pay rent; on time, always."
    assert rows[2][0] == ""


def test_summary_next_action(tmp_path):
    r = Report(tmp_path / "lease.pdf", "pdf", 2, events=[ev()])
    out = summary([r], date(2026, 10, 21))
    assert "lease.pdf (2 pages)" in out
    assert "Next action: Deadline for lease.pdf on 2027-01-15 (86 days from 2026-10-21)" in out
