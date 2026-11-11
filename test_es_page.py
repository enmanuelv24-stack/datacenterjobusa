"""Pruebas de la página en español (/es/). Correr con: python test_es_page.py"""
import es_page as es


def job(state="TX", entry=True, lo=None, hi=None, company="Acme", openings=1, job_id=None):
    return {"state": state, "entry": entry, "hourly_min": lo, "hourly_max": hi, "company": company,
            "openings": openings, "job_id": job_id or f"{state}-{company}-{lo}-{entry}-{openings}"}


def test_summary_counts_openings_entry_and_employers():
    jobs = [job(openings=3, company="A"), job(entry=False, company="B", job_id="b"), job(state="AZ", company="A", job_id="c")]

    s = es.summary(jobs)

    assert (s["openings"], s["entry_openings"], s["employers"]) == (5, 4, 2)


def test_summary_pay_uses_medians_of_postings_with_pay():
    jobs = [job(lo=20, hi=30, job_id="1"), job(lo=24, hi=40, job_id="2"), job(lo=30, hi=50, job_id="3"), job(job_id="4")]

    s = es.summary(jobs)

    assert (s["lo"], s["hi"]) == (24, 40)


def test_summary_without_pay_has_no_range():
    assert es.summary([job()])["lo"] is None


def test_lede_states_numbers_in_spanish():
    text = es.lede({"openings": 1653, "entry_openings": 319, "employers": 29, "lo": 27.98, "hi": 44.04})

    assert "1,653 vacantes" in text and "319" in text and "29 empresas" in text
    assert "$27.98–$44.04 la hora" in text


def test_lede_without_pay_does_not_invent_a_range():
    text = es.lede({"openings": 10, "entry_openings": 2, "employers": 1, "lo": None, "hi": None})

    assert "$" not in text


def test_faq_is_spanish_and_mentions_requirements():
    faq = es.faq(319, {"lo": 27.98, "hi": 44.04})

    questions = " ".join(q for q, _ in faq)
    answers = " ".join(a for _, a in faq)
    assert "¿" in questions and "experiencia" in questions
    assert "GED" in answers and "319" in answers


if __name__ == "__main__":
    for name, fn in list(globals().items()):
        if name.startswith("test_"):
            fn()
    print("OK")
