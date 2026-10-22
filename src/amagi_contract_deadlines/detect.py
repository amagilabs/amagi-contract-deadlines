"""Find term, renewal, notice and option dates in one contract.

Two kinds of event come out of here:

* explicit: the date is written in the contract ("expires on December 31, 2028");
* computed: the contract gives a rule ("at least sixty (60) days before the end of
  the then-current term") and we apply it to a date we found elsewhere. Every
  computed event carries a plain-English ``basis`` showing the arithmetic.

When a rule needs a date the contract never states, the event is still reported,
with no date, so nothing silently drops out.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import date, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from .dates import Duration, find_dates, find_durations, shift
from .extract import Document
from .segment import Clause, clauses

# Event kinds.
EFFECTIVE = "effective"
COMMENCEMENT = "commencement"
WINDOW_OPENS = "window_opens"
NOTICE = "notice_deadline"
OPTION = "option_deadline"
DEADLINE = "deadline"
EXPIRATION = "expiration"
RENEWAL = "renewal"

LABELS = {
    EFFECTIVE: "Effective date",
    COMMENCEMENT: "Term starts",
    EXPIRATION: "Term ends",
    RENEWAL: "Auto-renews",
    NOTICE: "Notice deadline",
    OPTION: "Option exercise deadline",
    WINDOW_OPENS: "Notice window opens",
    DEADLINE: "Deadline",
}
# Kinds a person has to act on. These get calendar reminders.
ACTION_KINDS = {NOTICE, OPTION, WINDOW_OPENS, DEADLINE}


@dataclass
class Event:
    kind: str
    label: str
    date: Optional[date]
    document: str
    section: str
    page: str
    quote: str
    basis: str = ""
    computed: bool = False
    auto_renews: bool = False
    path: str = ""

    @property
    def is_action(self) -> bool:
        return self.kind in ACTION_KINDS


@dataclass
class Report:
    path: Path
    kind: str
    page_count: int
    events: List[Event] = field(default_factory=list)
    auto_renews: bool = False
    renewal_term: Optional[Duration] = None
    notes: List[str] = field(default_factory=list)
    # Notice periods measured from something that is not a calendar date
    # ("thirty (30) days prior to the effective date of any assignment").
    relative_notices: List[str] = field(default_factory=list)


# ---------------------------------------------------------------- patterns

_EXPIRY_LEAD = re.compile(
    r"\b(?:expir\w*|end(?:s|ing)?|terminat\w*|through|thru|until|to\s+and\s+including)\b", re.I)
_STRONG_EXPIRY_LEAD = re.compile(r"\b(?:expir\w*|end\s+date|termination\s+date)\b", re.I)
_COMMENCE_LEAD = re.compile(r"\b(?:commenc\w*|begin\w*|start\w*|from)\b", re.I)
_EFFECTIVE_LEAD = re.compile(
    r"\beffective(?:\s+date)?\b[^.;]{0,30}?(?:as\s+of|on|is|shall\s+be|:|means)?\s*$"
    r"|\bdated(?:\s+as\s+of)?\s*$"
    r"|\b(?:entered\s+into|made)\b[^.;]{0,15}?(?:as\s+of|on|this)\s*$"
    r"|\bas\s+of\s*$",
    re.I)
_DEADLINE_LEAD = re.compile(
    r"(?:\bon\s+or\s+before|\bno\s+later\s+than|\bnot\s+later\s+than|\bprior\s+to|\bbefore|\bby)\s*$",
    re.I)
_TERM_CONTEXT = re.compile(
    r"\b(?:term|expir\w*|commenc\w*|effective\s+date|lease|agreement|contract)\b", re.I)

_AUTO_RENEW = re.compile(
    r"\bautomatic(?:ally)?\s+(?:be\s+)?(?:renew|extend)\w*"
    r"|\b(?:renew|extend)\w*\s+automatically"
    r"|\bauto[\s-]?renew\w*"
    r"|\bevergreen\b"
    r"|\bshall\s+(?:continue|renew|be\s+renewed|be\s+extended)\s+(?:thereafter\s+)?for\s+"
    r"(?:successive|additional|consecutive)\b[^.]{0,120}?\bunless\b",
    re.I)
# What has to be renewing for it to count: the contract or its term.
_AUTO_SUBJECT = re.compile(
    r"\b(?:term|agreement|lease|contract|subscription|sow|statement\s+of\s+work|order\s+form)\b",
    re.I)
# Things that auto-renew inside a contract but are not the contract itself.
_AUTO_NOT_CONTRACT = re.compile(
    r"letter\s+of\s+credit|\bL-?C\b|insurance|\bpolic(?:y|ies)\b|coverage|reporting\s+period"
    r"|business\s+day|\bbond\b|guarant", re.I)
_OPTION = re.compile(
    r"\boptions?\b[^.]{0,80}?\b(?:extend|renew|purchase|expand|terminate|buy)\w*"
    r"|\bright\s+(?:of\s+first\s+refusal|to\s+(?:extend|renew|purchase|expand|buy))"
    r"|\bexercis\w*\s+(?:the\s+|this\s+|such\s+|its\s+|each\s+|an\s+|any\s+)?(?:\w+\s+)?options?\b",
    re.I)
_OBLIGATION = re.compile(r"\b(?:shall|must|will|agrees?|required|due|may)\b", re.I)
_WINDOW_LINK = re.compile(
    r"^\s*,?\s*(?:and|nor|but|or)\s+(?:(?:not|no)\s+)?(?:less|later|fewer|sooner)\s+than\s*$", re.I)
_NON_RENEWAL = re.compile(
    r"\bnon[\s-]?renew\w*|\bnot\s+to\s+(?:renew|extend)|\belect\w*\s+not\s+to\b"
    r"|\bcancel\w*|\bterminat\w*", re.I)
# The rule applies to every term, not just the first one.
_EVERY_TERM = re.compile(r"(?:each|any|every)\s+(?:renewal|extension|subsequent)"
                         r"|then[\s-]+current\s+term", re.I)
_PRICE_CHANGE = re.compile(r"\b(?:increase|adjust|change)\w*\s+(?:the\s+|its\s+|any\s+)?"
                           r"(?:fees?|prices?|pricing|rates?|rent|charges?)\b", re.I)

_TERM_LEAD = re.compile(
    r"(?:\bterm\b|\bperiod\b)[^.;]{0,40}?\b(?:of|shall\s+be|is|be|for)\s*"
    r"(?:approximately\s+|an?\s+)?$"
    r"|\bterm\s*:\s*$"
    r"|\bfor\s+(?:a|an|the)?\s*(?:initial\s+)?(?:term|period)?\s*(?:of\s+)?$",
    re.I)
_RENEW_LEAD = re.compile(
    r"\b(?:successive|additional|consecutive|renewal|extension|extended|renewed|extend|renew)\b"
    r"[^.;]{0,40}$",
    re.I)
_NOTICE_AFTER = re.compile(
    r"^\s*['’]?\s*(?:(?:prior|advance|written|advanced)\s+){0,3}"
    r"(?:notice\s+)?(?:(?:of|to)\s+[\w-]+(?:\s+[\w-]+)?\s+)?"
    r"(?P<rel>prior\s+to|before|in\s+advance\s+of|preceding|ahead\s+of)\b(?P<anchor>.{0,140})",
    re.I | re.S)
_OPEN_QUALIFIER = re.compile(
    r"\b(?:no|not)\s+(?:more|earlier|sooner|greater)\s+than\s*$|\bmore\s+than\s*$", re.I)
_RENEWAL_ANCHOR = re.compile(
    r"^\W*(?:the\s+)?(?:each\s+|any\s+)?(?:renewal\s+date|anniversary|commencement\s+of\s+(?:the\s+|any\s+|each\s+)?"
    r"(?:renewal|extension|extended|next)|start\s+of\s+(?:the\s+|any\s+|each\s+)?(?:renewal|next))",
    re.I)
_EXPIRY_ANCHOR = re.compile(
    r"^\W*(?:the\s+|each\s+|any\s+|such\s+)?(?:"
    r"(?:scheduled\s+|then[\s-]+(?:current\s+|applicable\s+)?|initial\s+|original\s+)*"
    r"(?:expir\w*|end|termination)\b[^.;]{0,40}?\b(?:term|lease|agreement|contract|period|sow)\b"
    r"|(?:lease\s+|agreement\s+|initial\s+|then[\s-]+current\s+)?(?:expiration|end|termination)\s+date"
    r"|last\s+day\s+of\s+the\s+(?:then[\s-]+)?(?:current\s+|initial\s+)?term"
    r"|renewal\s+date|anniversary"
    r"|commencement\s+of\s+(?:the\s+|any\s+|each\s+)?(?:renewal|extension|extended|next)"
    r"|then[\s-]+current\s+term)",
    re.I)


def _last_match_end(pattern: "re.Pattern[str]", text: str) -> int:
    best = -1
    for m in pattern.finditer(text):
        best = m.end()
    return best


def _classify_date(lead: str) -> Optional[str]:
    """Which kind of date does the text right before it introduce?"""
    if _DEADLINE_LEAD.search(lead):
        return DEADLINE
    if _EFFECTIVE_LEAD.search(lead):
        return EFFECTIVE
    scores = {
        EXPIRATION: _last_match_end(_EXPIRY_LEAD, lead),
        COMMENCEMENT: _last_match_end(_COMMENCE_LEAD, lead),
    }
    kind, pos = max(scores.items(), key=lambda kv: kv[1])
    return kind if pos >= 0 else None


def is_auto_renewal(text: str) -> bool:
    """Does this sentence say the contract (not a letter of credit or policy) auto-renews?"""
    m = _AUTO_RENEW.search(text)
    if not m:
        return False
    window = text[max(0, m.start() - 150):m.end() + 60]
    return bool(_AUTO_SUBJECT.search(window)) and not _AUTO_NOT_CONTRACT.search(window)


def _where(ev) -> str:
    return " ".join(x for x in (f"§{ev.section}" if ev.section else "", f"p.{ev.page}") if x)


def _short(text: str, width: int = 80) -> str:
    text = " ".join(text.split())
    return text if len(text) <= width else text[: width - 1].rstrip() + "…"


# ---------------------------------------------------------------- analysis

@dataclass
class _Rule:
    """A notice rule waiting for its anchor date."""
    kind: str
    duration: Duration
    to_renewal: bool  # measured back from the first day of the next term
    anchor_date: Optional[date]
    anchor_text: str
    clause: Clause
    renewing: bool  # part of an auto-renewal clause, so it repeats every term


@dataclass
class _Candidate:
    event: Event
    strong: bool  # "expires on", "End Date:" rather than "through" or "until"


def analyze(doc: Document, as_of: Optional[date] = None) -> Report:
    as_of = as_of or date.today()
    report = Report(doc.path, doc.kind, doc.page_count)
    name = doc.path.name
    items = clauses(doc)

    def event(kind, when, clause, basis="", computed=False, label=None):
        return Event(kind, label or LABELS[kind], when, name, clause.section, clause.page,
                     clause.text, basis, computed, path=str(doc.path))

    explicit: List[Event] = []
    ends: List[_Candidate] = []
    terms: List[Tuple[Duration, Clause, Optional[date]]] = []
    rules: List[_Rule] = []
    auto_paragraphs = {c.paragraph for c in items if is_auto_renewal(c.text)}
    auto_clause = next((c for c in items if is_auto_renewal(c.text)), None)
    report.auto_renews = auto_clause is not None

    for clause in items:
        text = clause.text
        is_option = bool(_OPTION.search(text) or _OPTION.search(clause.paragraph))
        auto = is_auto_renewal(text)

        # Explicit dates.
        prev_end = 0
        start_in_clause: Optional[date] = None
        for hit in find_dates(text):
            lead = text[max(prev_end, hit.start - 80):hit.start]
            prev_end = hit.end
            kind = _classify_date(lead)
            if kind is None:
                continue
            if kind == DEADLINE:
                if not _OBLIGATION.search(text):
                    continue  # "before January 1" with no obligation word is usually a recital
                kind = OPTION if is_option else DEADLINE
            elif not _TERM_CONTEXT.search(text):
                continue
            ev = event(kind, hit.value, clause)
            if kind == COMMENCEMENT:
                start_in_clause = hit.value
            if kind == EXPIRATION:
                ends.append(_Candidate(ev, bool(_STRONG_EXPIRY_LEAD.search(lead))))
            explicit.append(ev)

        # Durations: term length, renewal length, notice periods.
        durations = find_durations(text)
        for index, dur in enumerate(durations):
            before = text[max(0, dur.start - 60):dur.start]
            notice = _NOTICE_AFTER.match(text[dur.end:])
            if not notice and _OPEN_QUALIFIER.search(before) and index + 1 < len(durations):
                # "not more than twelve (12) months and not less than nine (9) months
                # prior to the expiration": the first duration borrows the second's anchor.
                nxt = durations[index + 1]
                if _WINDOW_LINK.match(text[dur.end:nxt.start]):
                    notice = _NOTICE_AFTER.match(text[nxt.end:])
            if notice:
                anchor = notice.group("anchor")
                kind = OPTION if is_option else NOTICE
                if _OPEN_QUALIFIER.search(before):
                    kind = WINDOW_OPENS
                anchor_hit = find_dates(anchor[:60])
                anchor_date = anchor_hit[0].value if anchor_hit and anchor_hit[0].start < 25 else None
                if anchor_date is None and not _EXPIRY_ANCHOR.search(anchor):
                    report.relative_notices.append(
                        f"{_where(event(NOTICE, None, clause))}: {dur.text} before "
                        f"'{_short(anchor, 60)}'")
                    continue
                renewing = (not is_option) and report.auto_renews and (
                    auto or clause.paragraph in auto_paragraphs
                    or bool(_EVERY_TERM.search(text)) or bool(_RENEWAL_ANCHOR.search(anchor)))
                rules.append(_Rule(kind, dur.value, bool(_RENEWAL_ANCHOR.search(anchor)),
                                   anchor_date, _short(anchor, 70), clause, renewing))
                continue
            if _RENEW_LEAD.search(before[-45:]):
                if auto and report.renewal_term is None:
                    report.renewal_term = dur.value
                continue
            if _TERM_LEAD.search(before) and re.search(r"\bterm\b|\bperiod\b", before, re.I) \
                    and not dur.value.business:
                terms.append((dur.value, clause, start_in_clause))

        if auto and report.renewal_term is None:
            for dur in durations:
                if _RENEW_LEAD.search(text[max(0, dur.start - 45):dur.start]):
                    report.renewal_term = dur.value
                    break

    # A contract has one effective date. Exhibits and amendment histories add more
    # ("dated as of", "effective as of"); keep the first and count the rest.
    effectives = [ev for ev in explicit if ev.kind == EFFECTIVE]
    if len(effectives) > 1:
        extra = {id(ev) for ev in effectives[1:]}
        explicit = [ev for ev in explicit if id(ev) not in extra]
        report.notes.append(
            f"{len(effectives) - 1} more 'dated' or 'effective as of' date(s) left out, likely "
            "amendments or exhibits; see the clause text if they matter.")

    # ---- the term: when it starts and when it ends
    def first(kind):
        return next((ev for ev in explicit if ev.kind == kind), None)

    effective, commencement = first(EFFECTIVE), first(COMMENCEMENT)
    term_start = commencement or effective
    term_end: Optional[date] = None
    events: List[Event] = list(explicit)

    if ends:
        # Amendments and phased leases state several end dates. Prefer ones written
        # as an expiration ("expires on", "End Date:"), and of those the latest,
        # since extensions only push the end date out.
        pool = [c for c in ends if c.strong] or ends
        chosen = max(pool, key=lambda c: c.event.date)
        term_end = chosen.event.date
        others = sorted({c.event.date for c in ends} - {term_end})
        if others:
            report.notes.append(
                f"{len(others) + 1} end dates found; notice dates are measured from "
                f"{term_end.isoformat()} ({_where(chosen.event)}). Check which term is current.")
    elif terms:
        duration, clause, local_start = terms[0]
        start_ev = None
        if local_start:
            start_value, source = local_start, "the start date in the same sentence"
        elif term_start:
            start_value = term_start.date
            source = "the effective date" if term_start.kind == EFFECTIVE else "the commencement date"
            start_ev = term_start
        else:
            start_value = None
        if start_value:
            term_end = shift(start_value, duration) - timedelta(days=1)
            basis = (f"{source} {start_value.isoformat()} + {duration}, minus 1 day "
                     "(a term ends the day before its anniversary)")
            if start_ev is not None:
                basis += f"; start date from {_where(start_ev)}"
            events.append(event(EXPIRATION, term_end, clause, basis, computed=True))
        else:
            events.append(event(EXPIRATION, None, clause,
                                f"term of {duration}, but no start date was found", computed=True))

    # ---- renewal and notice dates
    renewal = report.renewal_term
    if auto_clause is not None and term_end:
        basis = "day after the term ends; the contract renews unless notice is given"
        if renewal:
            basis += f" (renewal term: {renewal})"
        events.append(event(RENEWAL, term_end + timedelta(days=1), auto_clause, basis,
                            computed=True))

    first_cycle: List[Event] = []
    for rule in rules:
        first_cycle.extend(_apply_rule(rule, term_end, event))
    events.extend(first_cycle)

    if auto_clause is not None and renewal and term_end:
        renewing = [r for r in rules if r.renewing and r.anchor_date is None]
        cycle_firsts = [ev for ev in first_cycle
                        if any(ev.quote == r.clause.text for r in renewing)]
        events.extend(_roll_forward(term_end, renewal, renewing, as_of, auto_clause, event,
                                    cycle_firsts))

    for ev in events:
        ev.auto_renews = report.auto_renews
    report.events = _dedupe(events)
    if report.auto_renews and renewal is None:
        report.notes.append("renews automatically, but the renewal length was not found.")
    return report


def _rule_label(rule: _Rule) -> str:
    text = rule.clause.text
    if rule.kind == WINDOW_OPENS:
        return "Option window opens" if _OPTION.search(rule.clause.paragraph) else "Notice window opens"
    if rule.kind == OPTION:
        return LABELS[OPTION]
    if _PRICE_CHANGE.search(text):
        return "Price-change notice deadline"
    if _NON_RENEWAL.search(text) or rule.renewing:
        return "Non-renewal notice deadline"
    return LABELS[NOTICE]


def _apply_rule(rule, term_end, event, cycle=0):
    label = _rule_label(rule)
    if cycle:
        label += f" (renewal {cycle})"
    if rule.anchor_date:
        anchor, what = rule.anchor_date, rule.anchor_date.isoformat()
    elif term_end:
        if rule.to_renewal:
            anchor = term_end + timedelta(days=1)
            what = f"renewal date {anchor.isoformat()}"
        else:
            anchor, what = term_end, f"term end {term_end.isoformat()}"
    else:
        return [event(rule.kind, None, rule.clause,
                      f"{rule.duration} before '{rule.anchor_text}', but the contract's end "
                      "date was not found", computed=True, label=label)]
    when = shift(anchor, rule.duration, sign=-1)
    basis = f"{what} minus {rule.duration}"
    if rule.kind == WINDOW_OPENS:
        basis += " (earliest day notice counts)"
    else:
        basis += " (last day to give notice)"
    return [event(rule.kind, when, rule.clause, basis, computed=True, label=label)]


def _roll_forward(term_end, renewal, rules, as_of, renew_clause, event, first_cycle):
    """Add renewal terms of an auto-renewing contract until the next notice date is ahead.

    A renewal term is shown when it is still running on ``as_of`` or later. Rolling
    stops at the first term whose notice dates all fall on or after ``as_of``, so the
    calendar always holds the next notice you can still give.
    """
    out: List[Event] = []

    def settled(cycle_events, end):
        deadlines = [ev.date for ev in cycle_events if ev.date and ev.is_action]
        return end >= as_of and all(d >= as_of for d in deadlines)

    if settled(first_cycle, term_end):
        return out
    end, cycle = term_end, 0
    while cycle < 500:
        cycle += 1
        end = shift(end + timedelta(days=1), renewal) - timedelta(days=1)
        if end < as_of:
            continue
        cycle_events: List[Event] = []
        for rule in rules:
            cycle_events.extend(_apply_rule(rule, end, event, cycle=cycle))
        basis = (f"first term ended {term_end.isoformat()}; after {cycle} renewal(s) of "
                 f"{renewal} each, this term ends {end.isoformat()}")
        out.append(event(EXPIRATION, end, renew_clause, basis, computed=True,
                         label=f"Term ends (renewal {cycle})"))
        out.append(event(RENEWAL, end + timedelta(days=1), renew_clause,
                         f"renews again for {renewal} unless notice is given", computed=True,
                         label=f"Auto-renews (renewal {cycle + 1})"))
        out.extend(cycle_events)
        if settled(cycle_events, end):
            break
    return out


def _dedupe(events: List[Event]) -> List[Event]:
    seen: Dict[Tuple, Event] = {}
    for ev in events:
        key = (ev.kind, ev.date, ev.label) if ev.date else (ev.kind, ev.quote, ev.label)
        if key not in seen:
            seen[key] = ev
    return sorted(seen.values(), key=lambda e: (e.date is None, e.date or date.max, e.label))
