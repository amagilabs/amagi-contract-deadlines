from datetime import date

from conftest import AS_OF, dated

from amagi_deadlines.detect import NOTICE, OPTION, RENEWAL, WINDOW_OPENS, analyze, is_auto_renewal
from amagi_deadlines.extract import load


def report_for(examples, name):
    return analyze(load(examples / name), as_of=AS_OF)


# ---------------------------------------------------------------- shipped examples

def test_equipment_lease(examples):
    r = report_for(examples, "equipment_lease.txt")
    got = dated(r)
    assert got["Term starts"] == "2025-01-01"
    assert got["Term ends"] == "2027-12-31"
    assert got["Option exercise deadline"] == "2027-10-02"  # 90 days before expiry
    assert got["Deadline"] == "2028-01-15"  # equipment return
    assert not r.auto_renews
    option = next(ev for ev in r.events if ev.kind == OPTION)
    assert option.section == "4" and option.computed
    assert "ninety (90) days prior to the expiration" in option.quote
    assert "2027-12-31 minus 90 days" in option.basis


def test_office_lease_pdf_window(examples):
    r = report_for(examples, "office_lease.pdf")
    got = dated(r)
    assert got["Effective date"] == "2026-02-10"
    assert got["Term starts"] == "2026-03-01"
    # five years from March 1, 2026, ending the day before the anniversary
    assert got["Term ends"] == "2031-02-28"
    assert got["Option window opens"] == "2030-02-28"  # not more than 12 months before
    assert got["Option exercise deadline"] == "2030-05-28"  # not less than 9 months before
    assert got["Deadline"] == "2026-02-20"  # certificate of insurance, page 2
    deadline = next(ev for ev in r.events if ev.label == "Deadline")
    assert deadline.page == "2" and deadline.section == "5"


def test_saas_auto_renewal_rolls_forward(examples):
    r = report_for(examples, "saas_subscription.docx")
    assert r.auto_renews and str(r.renewal_term) == "1 year"
    got = dated(r)
    assert got["Term ends"] == "2025-11-14"
    assert got["Non-renewal notice deadline"] == "2025-09-15"
    assert got["Price-change notice deadline"] == "2025-08-17"
    # as of 2026-10-21 the renewal-1 notice date has passed, so it rolls to renewal 2
    assert got["Non-renewal notice deadline (renewal 1)"] == "2026-09-15"
    assert got["Non-renewal notice deadline (renewal 2)"] == "2027-09-15"
    assert got["Auto-renews (renewal 3)"] == "2027-11-15"
    assert "Non-renewal notice deadline (renewal 3)" not in got


def test_roll_forward_depends_on_as_of(examples):
    early = analyze(load(examples / "saas_subscription.docx"), as_of=date(2025, 6, 1))
    labels = {ev.label for ev in early.events}
    assert not any("(renewal" in label for label in labels)


# ---------------------------------------------------------------- rules

def test_explicit_expiry_with_notice(run):
    r = run("2. Term. This Agreement commences on January 1, 2026 and expires on "
            "December 31, 2026. Either party may terminate by giving written notice at least "
            "thirty (30) days prior to the expiration of the term.")
    got = dated(r)
    assert got["Term ends"] == "2026-12-31"
    assert got["Non-renewal notice deadline"] == "2026-12-01"


def test_notice_before_a_written_date(run):
    r = run("The Tenant shall give notice no later than sixty (60) days before "
            "June 30, 2027 if it wishes to extend the lease term.")
    notice = next(ev for ev in r.events if ev.kind in (NOTICE, OPTION) and ev.date)
    assert notice.date == date(2027, 5, 1)


def test_business_day_notice(run):
    r = run("This Agreement expires on October 30, 2026. Notice of non-renewal is "
            "due ten (10) business days prior to the expiration of this Agreement.")
    assert dated(r)["Non-renewal notice deadline"] == "2026-10-16"


def test_rule_without_end_date_is_kept_undated(run):
    r = run("This lease shall automatically renew for successive one (1) year terms unless "
            "Tenant gives notice at least ninety (90) days prior to the end of the then-current "
            "term.")
    undated = [ev for ev in r.events if ev.date is None]
    assert undated and "end date was not found" in undated[0].basis


def test_notice_from_non_calendar_event_is_counted_not_dated(run):
    r = run("This Agreement expires on December 31, 2027. Licensee shall give thirty (30) "
            "days prior written notice before any assignment of this Agreement.")
    assert len(r.relative_notices) == 1
    assert not any(ev.kind == NOTICE for ev in r.events)


def test_recital_dates_need_an_obligation_word(run):
    r = run("Before January 1, 2020, the parties operated under a prior agreement.")
    assert dated(r) == {}


def test_letters_of_credit_and_insurance_do_not_count_as_auto_renewal():
    assert not is_auto_renewal(
        "The Letter of Credit shall automatically renew for successive one-year periods.")
    assert not is_auto_renewal(
        "Tenant's insurance policy for the lease shall be automatically renewed each year.")
    assert is_auto_renewal(
        "This Agreement will automatically renew for successive one (1) year terms.")
    assert is_auto_renewal(
        "The term shall renew automatically for additional twelve month periods.")


def test_only_the_first_effective_date_is_kept(run):
    r = run("This Lease is dated as of May 1, 2020. Lease term: five (5) years.\n\n"
            "First Amendment to Lease dated as of June 1, 2021.\n\n"
            "Second Amendment to Lease dated as of July 1, 2022.")
    effective = [ev for ev in r.events if ev.label == "Effective date"]
    assert [ev.date for ev in effective] == [date(2020, 5, 1)]
    assert any("2 more" in note for note in r.notes)


def test_latest_strong_end_date_wins(run):
    r = run("The original term was scheduled to expire on March 31, 2025. By this amendment "
            "the term is extended and shall expire on March 31, 2028. Tenant shall give "
            "notice at least six (6) months prior to the expiration of the term.")
    assert dated(r)["Notice deadline"] == "2027-09-30"
    assert any("2 end dates" in note for note in r.notes)


def test_window_opens_for_not_more_than(run):
    r = run("This lease expires on June 30, 2030. Tenant may exercise its option to renew by "
            "notice given not more than one hundred eighty (180) days and not less than ninety "
            "(90) days prior to the expiration of the term.")
    kinds = {ev.kind: ev.date for ev in r.events if ev.date}
    assert kinds[WINDOW_OPENS] == date(2030, 1, 1)
    assert kinds[OPTION] == date(2030, 4, 1)


def test_renewal_event_is_day_after_term_end(run):
    r = run("This Agreement is effective as of April 1, 2026. The initial term of this "
            "Agreement is twelve (12) months, starting on the Effective Date. This Agreement "
            "will automatically renew for successive one (1) year terms unless either party "
            "gives notice of non-renewal at least thirty (30) days before the end of the "
            "then-current term.")
    renew = next(ev for ev in r.events if ev.kind == RENEWAL)
    assert renew.date == date(2027, 4, 1)
    assert dated(r)["Term ends"] == "2027-03-31"


def test_every_event_quotes_its_clause(examples):
    for name in ("equipment_lease.txt", "office_lease.pdf", "saas_subscription.docx"):
        for ev in report_for(examples, name).events:
            assert ev.quote and ev.page and ev.document == name
