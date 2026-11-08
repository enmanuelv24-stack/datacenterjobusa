"""Página "Military & veteran data center jobs": vacantes SkillBridge y puestos que piden militares/veteranos.

Se genera cada día desde data/jobs.json, así que la lista siempre está al día. La guía corta solo afirma
lo que dicen las propias ofertas (p. ej. los requisitos del programa SkillBridge de Equinix) y lo básico
del programa SkillBridge del Departamento de Defensa.
"""
from __future__ import annotations

import html
import json
import re
import statistics
from collections import Counter

from site_config import SITE_NAME

E = html.escape
PATH = "military-veteran-data-center-jobs.html"
MILITARY_RE = re.compile(r"skillbridge|veteran|military|transitioning service", re.I)
SKILLBRIDGE_RE = re.compile(r"skillbridge", re.I)
MIN_PAID_FOR_RANGE = 3


def is_military(job: dict) -> bool:
    """La oferta está dirigida a militares en transición o veteranos (por su título)."""
    return bool(MILITARY_RE.search(job.get("title") or ""))


def _pay_range(jobs: list[dict]) -> str:
    paid = [j for j in jobs if j.get("hourly_min")]
    if len(paid) < MIN_PAID_FOR_RANGE:
        return ""
    lo = statistics.median(j["hourly_min"] for j in paid)
    hi = statistics.median(j.get("hourly_max") or j["hourly_min"] for j in paid)
    return f"${lo:,.2f}–${hi:,.2f}/hr"


def _names(names: list[str], more: bool) -> str:
    """"A, B and C" o "A, B, C and more"."""
    if more:
        return ", ".join(names) + " and more"
    return names[0] if len(names) == 1 else ", ".join(names[:-1]) + " and " + names[-1]


FAQ = [
    ("What is DoD SkillBridge?",
     "A Department of Defense program that lets service members in their last 180 days of service train or intern with a civilian employer "
     "while still receiving military pay and benefits. It needs approval from your unit commander, so start the paperwork early."),
    ("Who can apply to a data center SkillBridge program?",
     "Each employer sets its own rules. Equinix's data center technician cohort, for example, is for active-duty members or military spouses "
     "approved for SkillBridge or MSCAP, within or nearing their 180-day separation window, with a high school diploma and 2–4 years of related technical experience."),
    ("Do I need a technical MOS?",
     "Not always. Equinix accepts a technical or non-technical MOS, NEC or AFSC. Electrical, HVAC, power generation, communications and IT backgrounds "
     "map most directly to data center technician and critical facilities roles."),
    ("I'm already out. Can I still apply?",
     "SkillBridge is only for members still on active duty. Veterans can apply to the regular openings below; several employers mark them "
     "\"Military & Veterans Encouraged\" and many value military maintenance and electrical experience over a degree."),
]


def veteran_page(jobs: list[dict], job_list, signup_html: str) -> dict | None:
    """Devuelve los argumentos de Site.page() para la página de militares y veteranos (None si no hay vacantes)."""
    mil = sorted([j for j in jobs if is_military(j)], key=lambda j: (not SKILLBRIDGE_RE.search(j["title"]), -(j.get("hourly_max") or 0)))
    if not mil:
        return None
    n_open = sum(j["openings"] for j in mil)
    n_sb = sum(1 for j in mil if SKILLBRIDGE_RE.search(j["title"]))
    cos = Counter(j["company"] for j in mil)
    pay = _pay_range([j for j in mil if not SKILLBRIDGE_RE.search(j["title"])])
    co_list = ", ".join(f"{E(c)} ({n})" for c, n in cos.most_common())
    faq_html = "".join(f"<details><summary>{E(q)}</summary><p>{E(a)}</p></details>" for q, a in FAQ)
    faq_ld = json.dumps({"@context": "https://schema.org", "@type": "FAQPage", "mainEntity": [
        {"@type": "Question", "name": q, "acceptedAnswer": {"@type": "Answer", "text": a}} for q, a in FAQ]})
    lede = (f"{n_open:,} open data center jobs aimed at transitioning service members and veterans"
            + (f", including {n_sb} DoD SkillBridge internships" if n_sb else "")
            + f", from {len(cos)} employers: {co_list}."
            + (f" Veteran-encouraged roles post a median of <b>{E(pay)}</b>." if pay else ""))
    body = ('<p class="crumbs"><a href="index.html">Jobs</a> / Military &amp; veterans</p>'
            '<h1>Data center jobs for military and veterans, including SkillBridge</h1>'
            f'<p class="lede">{lede} Updated every morning from the employers\' own career pages.</p>'
            '<section class="guide"><h2>Why the military path works</h2><div class="prose">'
            '<p>Data centers run on the same things the military trains for: power, cooling, generators, networks, checklists and shift work. '
            'Electricians, generator and HVAC mechanics, comms and IT specialists usually fit critical facilities and technician roles; '
            'anyone used to maintenance logs and 12-hour shifts adapts fast.</p>'
            '<p><b>Still on active duty?</b> Look at the SkillBridge listings first: you train at the data center during your last months of service '
            'while the military keeps paying you, and many cohorts convert to full-time jobs. Ask your unit about command approval before you apply.</p>'
            '<p><b>Already out?</b> Apply to the veteran-encouraged roles below and translate your MOS into plain words: what equipment you maintained, '
            'the voltages and systems, how many people you led. See the <a href="data-center-technician-resume.html">résumé guide</a> and '
            '<a href="certifications.html">certifications that help</a>.</p></div></section>'
            '<h2>Open military and veteran jobs</h2>' + job_list(mil, 0)
            + '<h2>Questions service members ask</h2><div class="faq">' + faq_html + '</div>'
            + '<p class="note">More: <a href="entry-level-jobs.html">entry-level jobs</a>, <a href="travel-jobs.html">jobs with per diem and housing</a>, '
              '<a href="how-to-become-a-data-center-technician.html">how to become a data center technician</a>.</p>'
            + signup_html)
    return {"path": PATH,
            "title": f"Military & Veteran Data Center Jobs and SkillBridge Programs | {SITE_NAME}",
            "desc": f"{n_open:,} data center jobs for transitioning service members and veterans"
                    + (" , including DoD SkillBridge internships" if n_sb else "").replace(" ,", ",")
                    + f", at {_names([c for c, _ in cos.most_common(3)], more=len(cos) > 3)}, with posted pay. Updated daily.",
            "body": body, "head_extra": f'<script type="application/ld+json">{faq_ld}</script>', "count": len(mil)}
