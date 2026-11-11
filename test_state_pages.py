"""Pruebas de las páginas por estado para búsquedas exactas. Correr con: python test_state_pages.py"""
import state_pages as sp


def job(state="TX", entry=False, lo=None, hi=None, company="Acme", city="Dallas", openings=1, job_id=None):
    return {"state": state, "entry": entry, "hourly_min": lo, "hourly_max": hi, "company": company,
            "city": city, "openings": openings, "job_id": job_id or f"{state}-{company}-{city}-{lo}-{entry}-{openings}"}


def test_entry_states_needs_enough_distinct_entry_jobs():
    jobs = [job("TX", True, job_id=f"t{i}") for i in range(3)] + [job("NV", True, openings=24, job_id="n1")]

    assert sp.entry_states(jobs) == ["TX"]


def test_entry_states_sorted_by_openings():
    jobs = ([job("TX", True, job_id=f"t{i}") for i in range(3)]
            + [job("AZ", True, openings=10, job_id=f"a{i}") for i in range(3)])

    assert sp.entry_states(jobs) == ["AZ", "TX"]


def test_salary_states_needs_enough_postings_with_pay():
    jobs = [job("VA", lo=25, hi=35, job_id=f"v{i}") for i in range(5)] + [job("OH", lo=20, hi=30, job_id=f"o{i}") for i in range(4)]

    assert sp.salary_states(jobs) == ["VA"]


def test_pay_stats_uses_medians_and_names_the_top_employer():
    rows = [job(lo=20, hi=30, company="A"), job(lo=24, hi=34, company="B"), job(lo=30, hi=50, company="C"), job()]

    s = sp.pay_stats(rows)

    assert (s["lo"], s["hi"], s["n"]) == (24, 34, 3)
    assert (s["top"], s["top_company"]) == (50, "C")


def test_pay_stats_is_none_without_pay():
    assert sp.pay_stats([job()]) is None


def test_salary_faq_states_the_numbers_and_yearly_equivalent():
    faq = sp.salary_faq("Texas", {"lo": 24.0, "hi": 34.0, "n": 72, "top": 56.73, "top_company": "Introl"}, 2026)

    q, a = faq[0]
    assert q == "How much do data center technicians make in Texas?"
    assert "$24.00–$34.00 per hour" in a and "$49,920–$70,720 a year" in a and "72" in a
    assert any("Introl" in a2 and "$56.73" in a2 for _, a2 in faq)


def test_entry_faq_without_pay_does_not_invent_numbers():
    faq = sp.entry_faq("Arizona", None, 75, ["Phoenix", "Mesa"])

    text = " ".join(a for _, a in faq)
    assert "Phoenix" in text and "75" in text
    assert "per hour" not in faq[1][1] or "don't post" in faq[1][1]


def test_paths_use_state_slug():
    assert sp.entry_path("New Mexico") == "entry-level/new-mexico.html"
    assert sp.salary_path("Texas") == "salaries/texas.html"


if __name__ == "__main__":
    for name, fn in list(globals().items()):
        if name.startswith("test_"):
            fn()
    print("OK")
