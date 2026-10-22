# amagi-contract-deadlines

Put every lease option and cancel-by date on your calendar. Point amagi-contract-deadlines at a folder of
contracts and leases (PDF, DOCX or TXT). It finds every renewal, notice-window, expiry and
option date, tells you which clause each one came from, and writes an `.ics` file you can drop
into Google Calendar, Outlook or Apple Calendar, plus a CSV for your spreadsheet. It runs on
your machine. No account, no API key, and your contracts never leave your computer.

Built for small-business owners, property managers and solo attorneys who track renewals in
their heads, on sticky notes, or not at all, and don't want to pay for a contract management
platform to get a reminder.

![demo](assets/demo.gif)

## Install

```
pipx install amagi-contract-deadlines
```

Not on PyPI yet. Until it is, install straight from GitHub:

```
pipx install git+https://github.com/amagilabs/amagi-contract-deadlines
```

Python 3.9 or newer.

## Usage

Run it from the `examples` folder that ships with the repo. It holds three made-up contracts: an
office lease (PDF), a software subscription that auto-renews (DOCX) and an equipment lease
(TXT).

```
$ amagi-contract-deadlines . --as-of 2026-10-21 -o out
equipment_lease.txt (1 page)
  2024-12-05  Effective date                           p.1
  2025-01-01  Term starts                              §2 p.1
  2027-10-02  Option exercise deadline                 §4 p.1  computed
  2027-12-31  Term ends                                §2 p.1
  2028-01-15  Deadline                                 §5 p.1
office_lease.pdf (2 pages)
  2026-02-10  Effective date                           p.1
  2026-02-20  Deadline                                 §5 p.2
  2026-03-01  Term starts                              §1 p.1
  2030-02-28  Option window opens                      §3 p.1  computed
  2030-05-28  Option exercise deadline                 §3 p.1  computed
  2031-02-28  Term ends                                §1 p.1  computed
saas_subscription.docx (1 page), auto-renews for 1 year
  2024-11-15  Effective date                           p.1
  2025-08-17  Price-change notice deadline             §2.3 p.1  computed
  2025-09-15  Non-renewal notice deadline              §2.2 p.1  computed
  2025-11-14  Term ends                                §2.1 p.1  computed
  2025-11-15  Auto-renews                              §2.2 p.1  computed
  2026-08-17  Price-change notice deadline (renewal 1) §2.3 p.1  computed
  2026-09-15  Non-renewal notice deadline (renewal 1)  §2.2 p.1  computed
  2026-11-14  Term ends (renewal 1)                    §2.2 p.1  computed
  2026-11-15  Auto-renews (renewal 2)                  §2.2 p.1  computed
  2027-08-17  Price-change notice deadline (renewal 2) §2.3 p.1  computed
  2027-09-15  Non-renewal notice deadline (renewal 2)  §2.2 p.1  computed
  2027-11-14  Term ends (renewal 2)                    §2.2 p.1  computed
  2027-11-15  Auto-renews (renewal 3)                  §2.2 p.1  computed

Next action: Price-change notice deadline (renewal 2) for saas_subscription.docx on 2027-08-17 (300 days from 2026-10-21)

24 dated event(s) from 3 document(s)
Wrote out/deadlines.ics
Wrote out/deadlines.csv
```

`--as-of` pins "today" so you get the same output shown here. Leave it off and the tool uses
today's date.

Look at what it worked out on its own:

- **The office lease** never states an end date. It says the term is five years from March 1,
  2026, so the tool puts the end on February 28, 2031. The option clause says notice must go
  out "not more than twelve (12) months and not less than nine (9) months prior to the
  expiration", so you get both edges of the window: opens 2030-02-28, closes 2030-05-28.
- **The subscription** renews every year unless someone cancels at least sixty days before the
  term ends. The first two cancel-by dates have already passed, so the tool rolls the contract
  forward until it reaches the next one you can still meet: 2027-09-15.
- **The equipment lease** gives you 90 days before December 31, 2027 to buy the printer, so the
  last day to send notice is October 2, 2027.

Every computed date shows its arithmetic. In the CSV and in each calendar event:

```
Option exercise deadline for equipment_lease.txt.
How it was worked out: term end 2027-12-31 minus 90 days (last day to give notice)
Source: equipment_lease.txt, section 4, page 1
Clause: "Lessee may exercise this option by giving Lessor written notice no later than ninety (90) days prior to the expiration of the term."
```

Notice deadlines, option deadlines, windows opening and "on or before" dates get calendar
reminders 30 and 7 days ahead. Term starts and ends go on the calendar without alarms.

The CSV has one row per event with these columns: date, event, document, section, page,
computed, basis, auto_renews, clause, path. Events the tool found a rule for but couldn't date
show up there with a blank date, so nothing silently drops out.

### Options

```
amagi-contract-deadlines FOLDER                     read every .pdf, .docx and .txt in FOLDER and its subfolders
amagi-contract-deadlines a.pdf b.docx               read just these files
amagi-contract-deadlines FOLDER -o out/             write out/deadlines.ics and out/deadlines.csv
amagi-contract-deadlines FOLDER --name leases       name them leases.ics and leases.csv
amagi-contract-deadlines FOLDER --as-of 2026-10-21  treat that date as today
amagi-contract-deadlines FOLDER --upcoming          leave out dates that have already passed
amagi-contract-deadlines FOLDER --remind 60,30,7    reminders 60, 30 and 7 days ahead
amagi-contract-deadlines FOLDER --remind none       no reminders
amagi-contract-deadlines FOLDER --no-ics            CSV only
amagi-contract-deadlines FOLDER --no-csv            calendar only
amagi-contract-deadlines FOLDER --json              print JSON, write nothing
amagi-contract-deadlines FOLDER --no-recursive      skip subfolders
```

The exit code is 0 on success (files it couldn't read are listed and skipped), 1 if there were
no contracts to read or none could be read, and 2 for a bad option.

## What it finds

- **Term dates.** Start, effective and end dates written in the contract, and end dates it
  works out from a term length such as "five (5) years" plus the start date.
- **Auto-renewal.** Clauses like "will automatically renew for successive one (1) year renewal
  terms". The tool adds the renewal date and rolls the contract forward to the renewal term
  you're in now. It ignores letters of credit and insurance policies that renew, because those
  aren't the contract.
- **Notice deadlines.** Periods like "at least sixty (60) days before the end of the
  then-current term" or "no later than ninety (90) days prior to the expiration", in calendar
  days, business days, weeks, months or years. Price-change and non-renewal notices are labeled
  as such.
- **Notice windows.** "Not more than twelve (12) months and not less than nine (9) months prior
  to the expiration" gives an opening date and a closing date.
- **Options.** Options to extend, renew, purchase or expand are labeled as option deadlines.
- **Hard deadlines.** Obligations with a date attached, like "deliver a certificate of insurance
  to Landlord on or before February 20, 2026".

## Limits

amagi-contract-deadlines reads the words of the contract. It gives you a strong first draft of your
deadline calendar, not legal advice, so check each date against the signed document before you
rely on it.

- **Holidays and statutes.** It doesn't move a deadline for a holiday or apply state law, and
  "business days" means Monday to Friday.
- **Computed end dates** are the start date plus the term, minus one day. If the contract states
  an end date, that date wins.
- **Amendments and multi-part agreements** can state several end dates. Notice dates are measured
  from the latest one written as an expiration, and the summary prints a note telling you to
  check which term is current.
- **One effective date per document.** Later "dated as of" dates are usually amendments or
  exhibits; they're counted in a note, not added to the calendar.
- **Event-based notices,** such as notice due a set number of days before an assignment, have
  no fixed date, so they're counted in a note and listed in `--json` instead of going on the calendar.
- **Scanned PDFs** have no text to read. Run them through OCR first, for example
  `ocrmypdf scanned.pdf searchable.pdf`.
- **DOCX page numbers are estimates.** For exact pages, save as PDF and run that.

## Use it from Claude Code

The repo ships a [SKILL.md](SKILL.md). Copy it to `~/.claude/skills/amagi-contract-deadlines/SKILL.md`
and Claude Code will run amagi-contract-deadlines when you ask when a lease expires, which contracts
auto-renew, or to put your contract deadlines on a calendar.

It pairs with [amagi-legal-review-skills](https://github.com/amagilabs/amagi-legal-review-skills): those
skills review what a contract says, and this tool puts its dates on your calendar.

## Star it if it saved you a renewal

If amagi-contract-deadlines caught a cancel-by date you would have missed, a star helps other small
shops find it. Bug reports with a public contract that trips it up are the most useful thing
you can send.

## Other AmagiLabs projects

- [amagilabs on GitHub](https://github.com/amagilabs): the full catalog of small open-source
  tools from AmagiLabs (Amagisolutionsgroup, Inc.).
- [amagi-watch](https://github.com/amagilabs/amagi-watch): turns a video URL into something
  Claude can read (transcript, key frames and a timestamped index).
- [amagi-legal-review-skills](https://github.com/amagilabs/amagi-legal-review-skills): Claude Code skills
  for contract and lease review.

## Development

```
pip install -e ".[dev]"
pytest
python tests/make_examples.py   # rebuild the files in examples/
```

## License

MIT. See [LICENSE](LICENSE). Copyright (c) 2026 Amagisolutionsgroup, Inc. (AmagiLabs).
