"""Regenerate the sample contracts in examples/.

All three are made up: fictional parties, fictional addresses. Run from the
repo root:  python tests/make_examples.py
"""

from __future__ import annotations

import sys
import textwrap
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from minipdf import write_pdf  # noqa: E402

EXAMPLES = HERE.parent / "examples"

LEASE_PAGES = [
    [
        "OFFICE LEASE",
        "",
        "This Office Lease (this \"Lease\") is made and entered into as of February 10, 2026, by and",
        "between Juniper Row Properties LP (\"Landlord\") and Bright Harbor Dental, PLLC (\"Tenant\").",
        "",
        "1. BASIC LEASE TERMS",
        "Premises: Suite 210, 400 Example Avenue, Springfield",
        "Commencement Date: March 1, 2026",
        "Lease Term: Five (5) years",
        "Base Rent: $4,250.00 per month, increasing three percent (3%) on each anniversary of the",
        "Commencement Date.",
        "",
        "2. TERM",
        "The term of this Lease shall be five (5) years, beginning on the Commencement Date, unless",
        "sooner terminated as provided in this Lease.",
        "",
        "3. OPTION TO EXTEND",
        "Tenant shall have the option to extend the Term for one (1) additional period of five (5)",
        "years on the same terms, except that Base Rent shall be the then fair market rent. To exercise",
        "the option, Tenant must deliver written notice to Landlord not more than twelve (12) months",
        "and not less than nine (9) months prior to the expiration of the initial Term. If Tenant does",
        "not deliver timely notice, the option shall lapse.",
    ],
    [
        "4. HOLDOVER",
        "If Tenant remains in possession after the Term ends, Tenant shall pay holdover rent equal to",
        "one hundred fifty percent (150%) of the Base Rent then in effect.",
        "",
        "5. INSURANCE",
        "Tenant shall deliver a certificate of insurance to Landlord on or before February 20, 2026,",
        "and shall keep the required policies in force for the entire Term.",
        "",
        "6. NOTICES",
        "All notices under this Lease shall be in writing and delivered to the addresses listed on the",
        "signature page, with a copy by email to notices@example.com.",
        "",
        "7. EARLY TERMINATION",
        "Either party may terminate this Lease upon thirty (30) days' written notice following a",
        "casualty that renders the Premises untenantable.",
    ],
]

SAAS_PARAGRAPHS = [
    ("Title", "SOFTWARE SUBSCRIPTION AGREEMENT"),
    (None, "This Software Subscription Agreement (the \"Agreement\") is effective as of "
           "November 15, 2024 (the \"Effective Date\") between Ledgerline Cloud, Inc. "
           "(\"Provider\") and Pine Street Property Management LLC (\"Customer\")."),
    ("Heading 1", "1. Services"),
    (None, "Provider will provide Customer with access to the Ledgerline property accounting "
           "platform for up to 25 named users."),
    ("Heading 1", "2. Term and Renewal"),
    (None, "2.1 The initial term of this Agreement is twelve (12) months, starting on the "
           "Effective Date."),
    (None, "2.2 After the initial term, this Agreement will automatically renew for successive "
           "one (1) year renewal terms unless either party gives the other written notice of "
           "non-renewal at least sixty (60) days before the end of the then-current term."),
    (None, "2.3 Provider may increase fees for any renewal term by giving Customer notice at "
           "least ninety (90) days before the renewal date."),
    ("Heading 1", "3. Fees"),
    (None, "Customer will pay an annual subscription fee of $9,600, invoiced in advance and due "
           "within thirty (30) days after the invoice date."),
    ("Heading 1", "4. Termination for Cause"),
    (None, "Either party may terminate this Agreement if the other party materially breaches it "
           "and fails to cure the breach within thirty (30) days after written notice."),
]

EQUIPMENT_TEXT = """\
EQUIPMENT LEASE AGREEMENT

This Equipment Lease Agreement is dated December 5, 2024, between Tidewater Equipment
Finance Co. ("Lessor") and Cobalt Ridge Print Shop ("Lessee").

1. Equipment. Lessor leases to Lessee one wide-format printer, serial number EXAMPLE-0001.

2. Term. The lease term will commence on January 1, 2025 and expire on December 31, 2027.

3. Payments. Lessee shall pay $612.00 per month on the first day of each month.

4. Purchase Option. Lessee has the option to purchase the Equipment at the end of the
term for $1.00. Lessee may exercise this option by giving Lessor written notice no later
than ninety (90) days prior to the expiration of the term.

5. Return. If Lessee does not purchase the Equipment, Lessee shall return it to Lessor on
or before January 15, 2028, at Lessee's expense.
"""


def make_lease(path: Path) -> Path:
    return write_pdf(path, LEASE_PAGES)


def make_saas(path: Path) -> Path:
    from docx import Document

    doc = Document()
    for style, text in SAAS_PARAGRAPHS:
        if style:
            doc.add_paragraph(text, style=style)
        else:
            doc.add_paragraph(text)
    doc.save(str(path))
    return path


def make_equipment(path: Path) -> Path:
    path.write_text(EQUIPMENT_TEXT, encoding="utf-8")
    return path


def main() -> None:
    EXAMPLES.mkdir(exist_ok=True)
    for made in (
        make_lease(EXAMPLES / "office_lease.pdf"),
        make_saas(EXAMPLES / "saas_subscription.docx"),
        make_equipment(EXAMPLES / "equipment_lease.txt"),
    ):
        print(f"wrote {made.relative_to(HERE.parent)}")


if __name__ == "__main__":
    main()
