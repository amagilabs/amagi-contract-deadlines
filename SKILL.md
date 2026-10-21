---
name: amagi-deadlines
description: Pull renewal, notice-window, expiry and option dates out of a folder of contracts and leases (PDF, DOCX or TXT) with the local amagi-deadlines CLI. Every date comes with the section, page and clause it came from, and computed dates show the arithmetic. Writes an .ics calendar with reminders and a CSV. Use when asked when a contract or lease expires, when non-renewal notice is due, when an option to extend or purchase must be exercised, whether something auto-renews, or to put contract deadlines on a calendar. Runs offline, no API key.
---

# amagi-deadlines

A CLI that reads contracts and leases and writes their deadlines to a calendar:

- `deadlines.ics`: one all-day event per dated item. Action dates (notice deadlines, option
  deadlines, notice windows opening, "on or before" obligations) get reminders 30 and 7 days
  ahead by default.
- `deadlines.csv`: every event, including ones the tool could not date, with columns date,
  event, document, section, page, computed, basis, auto_renews, clause, path.

Explicit dates come from the text ("expires on December 31, 2027"). Computed dates come from a
rule applied to a date found elsewhere ("ninety (90) days prior to the expiration"), and the
`basis` column shows the arithmetic, for example `term end 2027-12-31 minus 90 days`.

## When to use this skill

- "When does this lease expire, and when do I have to give notice?"
- "Which of these vendor contracts auto-renew, and when is the cancel-by date?"
- "Put the option deadlines from these leases on my calendar."
- "Make me a spreadsheet of every renewal date in this folder."

## How to use it

1. Check it is installed: `amagi-deadlines --version`. If not: `pipx install amagi-deadlines`
   (or `pipx install .` from a clone of the repo).
2. Run it on files or folders (folders are searched recursively):
   - `amagi-deadlines contracts/ -o out` writes `out/deadlines.ics` and `out/deadlines.csv`
     and prints a summary per document.
   - `amagi-deadlines lease.pdf --json` prints everything as JSON and writes nothing. Use it when
     you need to reason over the events yourself.
   - `--as-of 2026-10-21` treats that date as today. Auto-renewing contracts are rolled forward
     to the next notice date still ahead of it.
   - `--upcoming` leaves out events dated before today (or `--as-of`).
   - `--remind 60,30,7` sets reminder days; `--remind none` turns them off.
   - `--name leases` changes the output file names; `--no-ics` / `--no-csv` skip one of them.
3. Read the summary back to the user: for each document, the term end, whether it auto-renews,
   and every notice or option deadline, with section and page. Finish with the "Next action"
   line the tool prints.
4. Point out every `note:` line. They flag documents with several end dates (amendments), notice
   periods tied to events with no fixed date, and auto-renewals with no renewal length found.
5. Point out events listed as "no date". The rule was found but the date it hangs on was not.
6. Always tell the user to check each date against the signed document. It is not legal advice.

## Exit codes

- 0: success, even if some files were skipped (they are listed on stderr).
- 1: no .pdf, .docx or .txt files found, or none of them could be read. A scanned PDF has no
  text layer; suggest `ocrmypdf input.pdf output.pdf`, then run again.
- 2: bad command-line arguments.

## Limits to mention when relevant

- It reads the words of the contract. It does not apply holiday calendars or statutes that move
  a deadline, and "business days" means Monday to Friday.
- A computed term end is the start date plus the term, minus one day. If the contract says the
  term ends on a specific date, that date wins.
- When a document has several end dates (an amendment history, a multi-SOW agreement), notice
  dates are measured from the latest one written as an expiration, and a note says so.
- Only the first "dated as of" or "effective as of" date is kept per document; later ones are
  usually amendments and are counted in a note.
- Notice periods measured from events with no fixed date (an assignment, a default, a casualty)
  are counted, not dated. `--json` lists them under `relative_notices`.
- DOCX page numbers are estimates. Saving as PDF gives exact pages.
- Pairs with the amagi legal-review skills: those review what a contract says; this tool puts
  its dates on a calendar.
