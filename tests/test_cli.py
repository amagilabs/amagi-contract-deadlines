import csv
import json
import shutil

import pytest

from amagi_contract_deadlines import __version__
from amagi_contract_deadlines.cli import main

AS_OF = ["--as-of", "2026-10-21"]


def read_csv(path):
    with open(path, encoding="utf-8-sig", newline="") as fh:
        return list(csv.DictReader(fh))


def test_examples_folder_writes_ics_and_csv(examples, tmp_path, capsys):
    assert main([str(examples), "-o", str(tmp_path), *AS_OF]) == 0
    out = capsys.readouterr().out
    assert "24 dated event(s) from 3 document(s)" in out
    assert "Next action:" in out
    ics = (tmp_path / "deadlines.ics").read_text(encoding="utf-8")
    assert ics.count("BEGIN:VEVENT") == 24
    rows = read_csv(tmp_path / "deadlines.csv")
    assert len(rows) == 24
    assert {r["document"] for r in rows} == {
        "equipment_lease.txt", "office_lease.pdf", "saas_subscription.docx"}


def test_json_writes_nothing(examples, tmp_path, capsys):
    path = str(examples / "equipment_lease.txt")
    assert main([path, "-o", str(tmp_path), "--json", *AS_OF]) == 0
    data = json.loads(capsys.readouterr().out)
    assert data["tool"] == "amagi-contract-deadlines" and data["version"] == __version__
    events = {e["event"]: e["date"] for e in data["documents"][0]["events"]}
    assert events["Option exercise deadline"] == "2027-10-02"
    assert list(tmp_path.iterdir()) == []


def test_upcoming_drops_past_events(examples, tmp_path):
    main([str(examples), "-o", str(tmp_path), "--upcoming", "--no-ics", "-q", *AS_OF])
    dates = [r["date"] for r in read_csv(tmp_path / "deadlines.csv") if r["date"]]
    assert dates and min(dates) >= "2026-10-21"


def test_remind_none_and_custom_name(examples, tmp_path):
    main([str(examples), "-o", str(tmp_path), "--remind", "none", "--name", "leases",
          "--no-csv", "-q", *AS_OF])
    ics = (tmp_path / "leases.ics").read_text(encoding="utf-8")
    assert "VALARM" not in ics
    assert not (tmp_path / "leases.csv").exists()


def test_custom_reminders(examples, tmp_path):
    main([str(examples / "equipment_lease.txt"), "-o", str(tmp_path), "--remind", "7,60",
          "-q", *AS_OF])
    ics = (tmp_path / "deadlines.ics").read_text(encoding="utf-8")
    assert "TRIGGER:-P60D" in ics and "TRIGGER:-P7D" in ics and "TRIGGER:-P30D" not in ics


def test_no_files_exits_1(tmp_path, capsys):
    assert main([str(tmp_path)]) == 1
    assert "no .pdf, .docx or .txt files" in capsys.readouterr().err


def test_unreadable_files_are_skipped(examples, tmp_path, capsys):
    shutil.copy(examples / "equipment_lease.txt", tmp_path / "good.txt")
    (tmp_path / "broken.pdf").write_bytes(b"not a pdf")
    assert main([str(tmp_path), "-o", str(tmp_path / "out"), *AS_OF]) == 0
    captured = capsys.readouterr()
    assert "skipped:" in captured.err and "1 file(s) skipped" in captured.out


def test_only_unreadable_files_exits_1(tmp_path):
    (tmp_path / "broken.pdf").write_bytes(b"not a pdf")
    assert main([str(tmp_path)]) == 1


def test_no_recursive(examples, tmp_path):
    nested = tmp_path / "a" / "b"
    nested.mkdir(parents=True)
    shutil.copy(examples / "equipment_lease.txt", nested / "lease.txt")
    assert main([str(tmp_path), "--no-recursive", "-o", str(tmp_path)]) == 1
    assert main([str(tmp_path), "-o", str(tmp_path / "out"), "-q", *AS_OF]) == 0


def test_bad_as_of_is_a_usage_error(examples, capsys):
    with pytest.raises(SystemExit) as exc:
        main([str(examples), "--as-of", "someday"])
    assert exc.value.code == 2
    assert "not a date" in capsys.readouterr().err
