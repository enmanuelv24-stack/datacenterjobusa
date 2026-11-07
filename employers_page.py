"""Páginas para empresas: "Employers" (planes) y "Post a job" (cómo publicar y pagar).

Flujo de pago sin servidor: el botón de cada plan abre un Payment Link de Stripe (JOB_PLANS[...]["pay_url"]).
En Stripe, configura "After payment → redirect" al formulario POST_JOB_URL para que la empresa mande los
datos del empleo. Con pay_url vacío el botón abre el formulario y se factura por correo (como antes).
"""
from __future__ import annotations

import html
import json

from site_config import JOB_PLANS, POST_JOB_URL, SITE_NAME

E = html.escape


def _plan_button(plan: dict, primary: bool) -> str:
    cls = "more primary" if primary else "more"
    if plan["pay_url"]:
        return (f'<p><a class="{cls}" href="{E(plan["pay_url"])}" rel="noopener" data-ev="plan" data-plan="{E(plan["name"])}">'
                f'Pay {E(plan["price"])} and post</a></p>'
                '<p class="note">Secure card payment by Stripe. Right after paying you fill in the job details.</p>')
    return (f'<p><a class="{cls}" href="{E(POST_JOB_URL)}" rel="noopener" target="_blank">Request {E(plan["name"].lower())}</a></p>'
            f'<p class="note">Write "{E(plan["name"].lower())}" in the notes field. We confirm within 24 hours and email the invoice.</p>')


def plans_html() -> str:
    """Tarjetas de los planes (el del medio destacado)."""
    cards = []
    for i, p in enumerate(JOB_PLANS):
        main = i == 1
        items = "".join(f"<li>{E(f)}</li>" for f in p["features"])
        cards.append(f'<section class="plan{" main" if main else ""}"><h2>{E(p["name"])}</h2>'
                     f'<p class="price">{E(p["price"])} <small>{E(p["term"])}</small></p><ul>{items}</ul>'
                     + _plan_button(p, main) + '</section>')
    return '<div class="plans">' + "".join(cards) + '</div>'


STEPS = ('<ol class="steps"><li><b>Pick a plan and pay</b> by card (or request an invoice).</li>'
         '<li><b>Send the job details</b> in a 2-minute form: pay, per diem, housing, schedule, start date, how to apply.</li>'
         '<li><b>Live within 24 hours</b>, linked straight to your phone, email or career page.</li></ol>')

WHAT_TO_INCLUDE = ('<h2>What to include</h2><div class="prose"><ul>'
                   '<li>Company, job title and project city/state</li><li>Hourly pay range and the overtime rule (after 40 or after 8)</li>'
                   '<li>Per diem ($/day, how many days) and housing (hotel paid, stipend, none)</li><li>Schedule (6×10, 6×12, rotation) and start date</li>'
                   '<li>How techs should apply: phone, email or link</li><li>Requirements: OSHA 10, certs, drug test, travel</li></ul></div>')

FAQ = [
    ("How do I pay?", "By card through Stripe when you pick a plan, or ask for an invoice in the form. No account needed."),
    ("How fast does it go live?", "Within 24 hours of receiving the job details, usually the same day."),
    ("Can I post more than one job?", "Yes. Each listing is one plan; for 5 or more openings a month, ask for the company page."),
    ("Do you share technicians' contact details?", "No. Technicians apply to you directly through the link, phone or email on your listing."),
    ("What if the job fills early?", "Tell us and it comes down the next morning. Remaining featured days can move to another opening."),
]


def _faq() -> tuple[str, str]:
    body = "".join(f"<details><summary>{E(q)}</summary><p>{E(a)}</p></details>" for q, a in FAQ)
    ld = json.dumps({"@context": "https://schema.org", "@type": "FAQPage", "mainEntity": [
        {"@type": "Question", "name": q, "acceptedAnswer": {"@type": "Answer", "text": a}} for q, a in FAQ]})
    return f'<h2>Questions</h2><div class="faq">{body}</div>', f'<script type="application/ld+json">{ld}</script>'


def employer_pages(jobs: list[dict], n_companies: int, signup_html: str, breadcrumbs) -> list[dict]:
    """Devuelve los argumentos de Site.page() para employers.html y post-a-job.html."""
    n_paid = sum(1 for j in jobs if j.get("hourly_min"))
    low = JOB_PLANS[0]["price"]
    faq_html, faq_ld = _faq()
    reach = (f'{SITE_NAME} lists {len(jobs):,} open technician jobs from {n_companies} employers today, {n_paid:,} with posted pay. '
             'It is read by working techs: fiber, cabling, electrical, critical facilities and DCT roles. '
             'Every listing links straight to you; we never collect applications or sell leads.')
    employers = ('<p class="crumbs"><a href="index.html">Jobs</a> / Employers</p>'
                 '<h1>Hire data center technicians who compare pay before they apply</h1>'
                 f'<p class="lede">{E(reach)}</p>' + plans_html() + '<h2>How it works</h2>' + STEPS
                 + '<section class="guide"><h2>Who posts here</h2><div class="prose">'
                 '<p>Contractors and subcontractors on data center builds (fiber, structured cabling, electrical, mechanical), staffing firms that place '
                 'technicians on hyperscale projects, and operators hiring critical facilities and DCT roles. Large employers such as Amazon, Microsoft, '
                 'Google, QTS and Equinix are read automatically from their career pages; paid plans are for companies that need the crew filled this month.</p>'
                 '<p><b>What techs read first:</b> hourly pay, per diem per day, housing, the schedule (6×10, 6×12, rotation) and the start date. '
                 'Listings that state all five get the most clicks. If you pay it, say it.</p>'
                 '<p><b>What we never publish:</b> site names, badge or access details, or your direct contact if you ask us to use a general line.</p>'
                 '</div></section>' + faq_html)
    post = ('<p class="crumbs"><a href="index.html">Jobs</a> / Post a job</p>'
            f'<h1>Post a data center job from {E(low)}</h1>'
            '<p class="lede">For contractors, subcontractors and staffing firms hiring data center technicians, cabling and fiber crews. '
            'Pick a plan, send the details, and techs see your pay, per diem and schedule within 24 hours.</p>'
            + STEPS + plans_html() + WHAT_TO_INCLUDE + faq_html + signup_html)
    crumbs = breadcrumbs([("Jobs", "index.html"), ("Employers", "employers.html")])
    return [
        {"path": "employers.html", "title": f"Hire Data Center Technicians: Job Listings from {low} | {SITE_NAME}",
         "desc": f"Reach data center technicians, fiber and cabling crews who compare pay before they apply. Job listings from {low}, featured listings, company pages. {len(jobs):,} open jobs listed today.",
         "body": employers, "head_extra": crumbs + faq_ld},
        {"path": "post-a-job.html", "title": f"Post a Data Center Job from {low}: Contractors, Subs and Staffing | {SITE_NAME}",
         "desc": "Post a job for data center technicians, cabling and fiber crews. Pay by card, live within 24 hours, linked straight to you.",
         "body": post, "head_extra": faq_ld},
    ]
