from amagi_deadlines.extract import load
from amagi_deadlines.segment import clauses, split_sentences


def test_sentences_respect_abbreviations():
    text = "Rent is due on the 1st, e.g. Jan. 1. Tenant pays Inc. fees. Done."
    spans = [text[a:b].strip() for a, b in split_sentences(text)]
    assert spans == ["Rent is due on the 1st, e.g. Jan. 1.", "Tenant pays Inc. fees.", "Done."]


def test_numbered_sections_and_pages(make_txt):
    path = make_txt(
        "LEASE\n\n2. Term. The term starts March 1, 2026. It ends later.\n"
        "\f3.1 Option. Tenant may extend.\n")
    found = clauses(load(path))
    by_text = {c.text: c for c in found}
    assert by_text["The term starts March 1, 2026."].section == "2"
    assert by_text["The term starts March 1, 2026."].page == "1"
    assert by_text["Tenant may extend."].section == "3.1"
    assert by_text["Tenant may extend."].page == "2"


def test_clause_keeps_its_paragraph(make_txt):
    path = make_txt("4. Purchase Option. Lessee has an option. Lessee may exercise it.\n")
    found = clauses(load(path))
    assert all("Lessee has an option." in c.paragraph for c in found)
