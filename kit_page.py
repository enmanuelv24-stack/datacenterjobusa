"""Página de venta del "Data Center Technician Job-Ready Kit" (producto digital en PDF).

El PDF no vive en este repositorio (es público): se vende y entrega en la tienda configurada en KIT_URL
(Gumroad, Lemon Squeezy, Stripe…). Con KIT_URL vacío la página dice "muy pronto" y recoge correos.
"""
from __future__ import annotations

import html
import json
import statistics

from site_config import KIT_PRICE, KIT_URL, SITE_NAME, SITE_URL

E = html.escape
PATH = "job-ready-kit.html"

CONTENTS = [
    ("The jobs and what they pay", "Median posted pay for each job family and level, from 1,000+ real listings."),
    ("Who hires beginners", "The employers with the most entry-level listings right now, and where the jobs are."),
    ("Certifications worth your money", "Which ones help on the IT side and the facilities side, and which to skip."),
    ("Your 30-day plan", "What to do each week, from OSHA 10 to your first interviews."),
    ("Résumé template", "A one-page template plus ready-made bullets for electricians, IT, military, cabling and warehouse backgrounds."),
    ("The 15 interview questions", "Technical and behavioral questions with answers that work, and what to ask them."),
    ("Comparing offers", "How to compare hourly pay, overtime, per diem and housing on travel jobs."),
    ("Application tracker", "A printable table to track every application and follow-up."),
]


def _entry_pay(jobs: list[dict]) -> str:
    """Mediana del rango por hora de los anuncios de entrada con salario publicado."""
    paid = [j for j in jobs if j.get("entry") and j.get("hourly_min")]
    if not paid:
        return ""
    lo = statistics.median(j["hourly_min"] for j in paid)
    hi = statistics.median(j.get("hourly_max") or j["hourly_min"] for j in paid)
    return f"${lo:,.2f}–${hi:,.2f}/hr"


def _buy_block(lead_form) -> str:
    if KIT_URL:
        return (f'<p><a class="more primary" href="{E(KIT_URL)}" rel="noopener" data-ev="kit">Get the kit — {E(KIT_PRICE)}</a></p>'
                '<p class="note">Instant PDF download. 12 pages, US Letter, prints well.</p>')
    return ('<p><b>Launching soon.</b> Leave your email and we will send you the kit link the day it is ready.</p>'
            + lead_form("kit", "Tell me when it's ready", page=PATH))


def _product_ld() -> str:
    if not KIT_URL:
        return ""
    price = "".join(ch for ch in KIT_PRICE if ch.isdigit() or ch == ".")
    ld = {"@context": "https://schema.org", "@type": "Product", "name": "Data Center Technician Job-Ready Kit 2026",
          "description": "PDF guide to landing a first data center technician job: pay data, employers hiring beginners, certifications, résumé template and interview questions.",
          "brand": {"@type": "Brand", "name": SITE_NAME}, "url": f"{SITE_URL}/{PATH}",
          "offers": {"@type": "Offer", "price": price, "priceCurrency": "USD", "availability": "https://schema.org/InStock", "url": KIT_URL}}
    return f'<script type="application/ld+json">{json.dumps(ld)}</script>'


def kit_page(jobs: list[dict], lead_form) -> dict:
    """Devuelve los argumentos de Site.page() para la página del kit."""
    n = len(jobs)
    n_cos = len({j["company"] for j in jobs})
    entry = _entry_pay(jobs)
    items = "".join(f"<li><b>{E(t)}.</b> {E(d)}</li>" for t, d in CONTENTS)
    faq = [
        ("Does the kit guarantee a job?", "No. Nothing can. It gives you the pay data, the employers hiring beginners, the résumé and the interview prep; "
         "applying fast and being flexible on shifts and travel is still on you."),
        ("Is this for people with no experience?", "Yes. It is written for people coming from the trades, IT help desk, the military, cabling crews or general labor."),
        ("Where does the data come from?", f"From the {n:,} listings on this site, read every morning from {n_cos} employers' own career pages."),
        ("What format is it?", "A 12-page PDF you download right after paying. It reads on a phone and prints on US Letter paper."),
    ]
    faq_html = "".join(f"<details><summary>{E(q)}</summary><p>{E(a)}</p></details>" for q, a in faq)
    body = ('<p class="crumbs"><a href="index.html">Jobs</a> / Job-Ready Kit</p>'
            '<h1>Data Center Technician Job-Ready Kit 2026</h1>'
            f'<p class="lede">The shortest honest route to your first data center job, built from {n:,} real listings at {n_cos} employers'
            + (f'. Entry-level listings with pay post a median of <b>{E(entry)}</b>.' if entry else '.') + '</p>'
            '<div class="plans"><section class="plan main"><h2>What you get</h2>'
            f'<p class="price">{E(KIT_PRICE)} <small>one-time · PDF</small></p>'
            f'<ul>{items}</ul>' + _buy_block(lead_form) + '</section></div>'
            '<section class="guide"><h2>Who it is for</h2><div class="prose">'
            '<p>Electricians, HVAC techs, help-desk and IT people, veterans, low-voltage and fiber crews, and anyone who wants a stable, well-paid hands-on job '
            'and is willing to work shifts or travel. If you already work in a data center, the pay tables and the offer comparison still help you negotiate.</p>'
            '<p>Prefer free? Everything on this site stays free: <a href="entry-level-jobs.html">entry-level jobs</a>, '
            '<a href="data-center-technician-resume.html">résumé guide</a>, <a href="data-center-technician-interview-questions.html">interview questions</a> '
            'and <a href="salaries.html">salaries</a>. The kit puts it all in one printable plan with the numbers.</p></div></section>'
            f'<h2>Questions</h2><div class="faq">{faq_html}</div>')
    faq_ld = '<script type="application/ld+json">' + json.dumps({"@context": "https://schema.org", "@type": "FAQPage", "mainEntity": [
        {"@type": "Question", "name": q, "acceptedAnswer": {"@type": "Answer", "text": a}} for q, a in faq]}) + '</script>'
    return {"path": PATH, "title": f"Data Center Technician Job-Ready Kit 2026: Pay, Employers, Résumé, Interview | {SITE_NAME}",
            "desc": "A printable kit to land your first data center technician job: real pay by job and level, employers hiring beginners, "
                    "certifications worth it, a résumé template and the 15 interview questions.",
            "body": body, "head_extra": _product_ld() + faq_ld}
