"""Páginas por estado para búsquedas exactas que la gente escribe en Google:
"entry level data center jobs Texas" y "data center technician salary Texas".

Aquí solo se decide qué estados merecen página (para no publicar páginas vacías) y se arman
las cifras y preguntas frecuentes. El HTML de la lista de vacantes lo pone build_site.py.
"""
from __future__ import annotations

import re
import statistics
from collections import Counter

MIN_ENTRY_JOBS = 3   # vacantes distintas para principiante que necesita un estado para tener página propia
MIN_PAID_JOBS = 5    # vacantes con paga publicada que necesita un estado para tener página de salarios
HOURS_PER_YEAR = 2080


def _slug(s: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", s.lower()).strip("-")


def entry_path(state_name: str) -> str:
    return f"entry-level/{_slug(state_name)}.html"


def salary_path(state_name: str) -> str:
    return f"salaries/{_slug(state_name)}.html"


def _states_with(jobs: list[dict], keep, minimum: int) -> list[str]:
    """Estados con al menos `minimum` vacantes distintas que cumplen `keep`, de más a menos puestos abiertos."""
    distinct: dict[str, set] = {}
    openings: Counter = Counter()
    for j in jobs:
        if j.get("state") and keep(j):
            distinct.setdefault(j["state"], set()).add(j["job_id"])
            openings[j["state"]] += j["openings"]
    return [s for s, _ in openings.most_common() if len(distinct[s]) >= minimum]


def entry_states(jobs: list[dict]) -> list[str]:
    return _states_with(jobs, lambda j: j.get("entry"), MIN_ENTRY_JOBS)


def salary_states(jobs: list[dict]) -> list[str]:
    return _states_with(jobs, lambda j: j.get("hourly_min"), MIN_PAID_JOBS)


def pay_stats(rows: list[dict]) -> dict | None:
    """Mediana del mínimo y del máximo publicados, y el rango más alto con su empleador. None si nadie publicó paga."""
    paid = [j for j in rows if j.get("hourly_min")]
    if not paid:
        return None
    best = max(paid, key=lambda j: j["hourly_max"] or 0)
    return {"lo": statistics.median(j["hourly_min"] for j in paid),
            "hi": statistics.median(j["hourly_max"] for j in paid),
            "n": len(paid), "top": best["hourly_max"], "top_company": best["company"]}


def _hr(v: float) -> str:
    return f"${v:,.2f}"


def _yr(v: float) -> str:
    return f"${v * HOURS_PER_YEAR:,.0f}"


def salary_faq(state: str, s: dict, year: int) -> list[tuple[str, str]]:
    return [
        (f"How much do data center technicians make in {state}?",
         f"Employers hiring in {state} post a typical range of {_hr(s['lo'])}–{_hr(s['hi'])} per hour "
         f"({_yr(s['lo'])}–{_yr(s['hi'])} a year at 40 hours), based on {s['n']} current postings that include pay."),
        (f"Who pays the most in {state} right now?",
         f"The highest posted range today tops out at {_hr(s['top'])} per hour, from {s['top_company']}. "
         "Contractor jobs often add overtime and per diem on top of the hourly rate, so the weekly check can beat a higher base."),
        (f"Is {year} a good time to start in {state}?",
         f"Data center construction keeps adding campuses, and contractors in {state} hire Level I techs and train on the job. "
         "Entry-level postings are listed on this site every day with the pay the employer wrote."),
        ("Where do these numbers come from?",
         "Only from the pay range in each employer's posting, read daily. Salaried ranges are divided by 2,080 hours. 'Typical' is the median; we never estimate."),
    ]


def entry_faq(state: str, s: dict | None, openings: int, cities: list[str]) -> list[tuple[str, str]]:
    where = ", ".join(cities[:4])
    pay = (f"Entry-level postings in {state} list a typical {_hr(s['lo'])}–{_hr(s['hi'])} per hour, the highest up to {_hr(s['top'])}."
           if s else f"Most entry-level employers in {state} don't post pay; ask the recruiter for the hourly rate, overtime and per diem before you accept.")
    return [
        (f"Can you get a data center job in {state} with no experience?",
         f"Yes. There are {openings} entry-level openings in {state} right now"
         + (f", mostly around {where}" if where else "")
         + ". Level I technicians, cable pullers and deployment techs are hired without data center experience."),
        (f"How much do entry-level data center jobs pay in {state}?", pay),
        ("What do employers ask for?",
         "A high school diploma or GED, a drug test and background check, the ability to lift 50 lb and work 10–12 hour shifts, and usually a driver's license. "
         "An OSHA 10 card helps on construction sites."),
    ]
