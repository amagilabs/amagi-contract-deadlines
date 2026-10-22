"""amagi-contract-deadlines command line."""

from __future__ import annotations

import argparse
import sys
from datetime import date
from pathlib import Path
from typing import List, Optional, Sequence

from . import __version__
from .dates import parse_date
from .detect import Report, analyze
from .extract import ExtractError, NoTextError, load
from .render import all_events, summary, to_csv, to_ics, to_json

SUFFIXES = {".pdf", ".docx", ".txt"}


def _collect(paths: Sequence[str], recursive: bool) -> List[Path]:
    files: List[Path] = []
    for raw in paths:
        path = Path(raw)
        if path.is_dir():
            pattern = "**/*" if recursive else "*"
            files += sorted(p for p in path.glob(pattern)
                            if p.is_file() and p.suffix.lower() in SUFFIXES
                            and not p.name.startswith(("~$", ".")))
        else:
            files.append(path)
    return files


def _as_of(value: str) -> date:
    parsed = parse_date(value)
    if parsed is None:
        raise argparse.ArgumentTypeError(f"not a date: {value!r} (use YYYY-MM-DD)")
    return parsed


def _remind(value: str) -> List[int]:
    if value.strip().lower() in ("", "none", "0"):
        return []
    try:
        days = sorted({int(part) for part in value.split(",") if part.strip()}, reverse=True)
    except ValueError:
        raise argparse.ArgumentTypeError(f"not a list of day counts: {value!r} (e.g. 30,7)")
    if any(d <= 0 for d in days):
        raise argparse.ArgumentTypeError("reminder days must be positive")
    return days


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="amagi-contract-deadlines",
        description=(
            "Pull renewal, notice-window, expiry and option dates out of contracts and "
            "leases (PDF, DOCX or TXT), with the clause each one came from. Writes an "
            ".ics calendar and a CSV."),
        epilog="Check every date against the signed document. This is not legal advice.",
    )
    p.add_argument("paths", nargs="+", metavar="PATH", help="contract files or folders")
    p.add_argument("-o", "--out", default=".", metavar="DIR",
                   help="folder to write the files to (default: current folder)")
    p.add_argument("--name", default="deadlines",
                   help="base name for the output files (default: deadlines)")
    p.add_argument("--as-of", type=_as_of, default=None, metavar="DATE",
                   help="treat this as today, for rolling auto-renewals forward (default: today)")
    p.add_argument("--remind", type=_remind, default=[30, 7], metavar="DAYS",
                   help="calendar reminders before each action date, e.g. 60,30,7 (default: 30,7; "
                        "'none' for no reminders)")
    p.add_argument("--upcoming", action="store_true",
                   help="leave out events dated before --as-of (or today)")
    p.add_argument("--no-ics", action="store_true", help="don't write the .ics file")
    p.add_argument("--no-csv", action="store_true", help="don't write the CSV file")
    p.add_argument("--json", action="store_true", help="print JSON and write nothing")
    p.add_argument("--no-recursive", action="store_true",
                   help="only read files directly inside the folders given")
    p.add_argument("-q", "--quiet", action="store_true", help="print only the file names written")
    p.add_argument("--version", action="version", version=f"amagi-contract-deadlines {__version__}")
    return p


def _utf8_stdout() -> None:
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except (AttributeError, ValueError):
            pass


def main(argv: Optional[Sequence[str]] = None) -> int:
    _utf8_stdout()
    args = build_parser().parse_args(argv)
    as_of = args.as_of or date.today()

    files = _collect(args.paths, not args.no_recursive)
    if not files:
        print("amagi-contract-deadlines: no .pdf, .docx or .txt files found", file=sys.stderr)
        return 1

    reports: List[Report] = []
    failed = 0
    for path in files:
        try:
            doc = load(path)
        except NoTextError as exc:
            print(f"skipped: {exc}", file=sys.stderr)
            failed += 1
            continue
        except ExtractError as exc:
            print(f"skipped: {exc}", file=sys.stderr)
            failed += 1
            continue
        reports.append(analyze(doc, as_of=as_of))

    if not reports:
        print("amagi-contract-deadlines: none of the files could be read", file=sys.stderr)
        return 1

    if args.upcoming:
        for report in reports:
            report.events = [ev for ev in report.events if ev.date is None or ev.date >= as_of]
    events = all_events(reports)
    if args.json:
        print(to_json(reports))
        return 0
    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)
    written: List[Path] = []
    if not args.no_ics:
        path = out_dir / f"{args.name}.ics"
        path.write_bytes(to_ics(events, remind_days=args.remind).encode("utf-8"))
        written.append(path)
    if not args.no_csv:
        path = out_dir / f"{args.name}.csv"
        # utf-8-sig so Excel opens accented names and section signs correctly
        path.write_text(to_csv(events), encoding="utf-8-sig", newline="")
        written.append(path)

    if not args.quiet:
        print(summary(reports, as_of))
        dated = sum(1 for ev in events if ev.date)
        undated = len(events) - dated
        line = f"\n{dated} dated event(s) from {len(reports)} document(s)"
        if undated:
            line += f", {undated} without a date (in the CSV only)"
        if failed:
            line += f"; {failed} file(s) skipped"
        print(line)
    for path in written:
        print(f"Wrote {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
