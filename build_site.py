"""
Genera el sitio estático a partir de data/jobs.json.

    python build_site.py                 # sitio completo en site/ (con una página por vacante)
    python build_site.py --preview out/  # versión ligera para vista previa (sin páginas por vacante)

Todo el sitio es HTML estático: se puede publicar gratis en Cloudflare Pages, Netlify o GitHub Pages.
"""
from __future__ import annotations

import argparse
import html
import json
import re
import statistics
from collections import Counter, defaultdict
from datetime import date, timedelta
from pathlib import Path

from site_config import (NEWSLETTER_ACTION, MIN_CITY_OPENINGS, SURVEY_URL, OWNER_BLURB, ROLE_EN, SITE_NAME, SITE_TAGLINE,
                         SITE_URL, STATE_NAMES)

E = html.escape


def slug(s: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", s.lower()).strip("-")


def money(v, unit="hour"):
    if v is None:
        return "—"
    return f"${v:,.2f}" if unit == "hour" else f"${v:,.0f}"


LOGO_COLORS = ["#0f766e", "#1e40af", "#6d28d9", "#b45309", "#b91c1c", "#0e7490", "#374151", "#be185d", "#1d4ed8", "#4d7c0f"]


COMPANY_DOMAINS = {
    "Amazon": "amazon.com", "M.C. Dean": "mcdean.com", "Oracle": "oracle.com", "xAI": "x.ai", "Google": "google.com",
    "Introl": "introl.com", "Black Box": "blackbox.com", "QTS": "qtsdatacenters.com", "E2 Optics": "e2optics.com",
    "TDS (Total Deployment Solutions)": "totaldeployment.com", "Microsoft": "microsoft.com", "Equinix": "equinix.com",
    "Vision Technologies": "visiontechnologies.com", "CoreWeave": "coreweave.com", "Holder Construction": "holderconstruction.com",
    "Rosendin": "rosendin.com", "Network Connex": "networkconnex.com", "AFL": "aflglobal.com", "Cologix": "cologix.com",
    "Nebius": "nebius.com", "Crusoe": "crusoe.ai", "ADB Companies": "adbcompanies.com", "Compu Dynamics": "compu-dynamics.com",
    "Lambda": "lambda.ai", "Team LINX": "teamlinx.com", "The Archetype Strategy": "archetypestrategy.com",
    "MidPoint Technology Group": "midpointtechnologygroup.com", "Align": "align.com", "Telvero": "telvero.com", "SRI Telecom": "sritelecom.net",
}


def logo(company: str) -> str:
    """Ícono del empleador (su propio favicon, servido por Google) sobre un avatar de letras de respaldo."""
    words = [w for w in re.split(r"[\s(]+", company) if w and w[0].isalpha()]
    txt = (words[0][:2] if len(words) == 1 else "".join(w[0] for w in words[:2])).upper()
    col = LOGO_COLORS[sum(map(ord, company)) % len(LOGO_COLORS)]
    dom = COMPANY_DOMAINS.get(company)
    img = (f'<img src="https://www.google.com/s2/favicons?domain={E(dom)}&amp;sz=64" alt="" width="44" height="44" loading="lazy" '
           f'onerror="this.remove()">' if dom else "")
    return f'<span class="logo" style="background:{col}" aria-hidden="true"><b>{E(txt)}</b>{img}</span>'


def clean_title(t: str) -> str:
    t = re.sub(r"\s+,", ",", t)
    t = re.sub(r",\s*(DCC Communities|Amazon Web Services|AWS Support|AWS)\b", "", t)
    return re.sub(r"\s{2,}", " ", t).strip(" ,-")


# ---------------------------------------------------------------------------
# Estilos y plantilla
# ---------------------------------------------------------------------------
CSS = (Path(__file__).with_name("theme.css")).read_text(encoding="utf-8")

FONTS = ('<link rel="preconnect" href="https://fonts.googleapis.com"><link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>'
         '<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Source+Sans+3:wght@400;600;700&display=swap">')


PERK_EN = {"per_diem": "Per diem", "housing": "Housing", "travel": "Travel", "overtime": "Overtime", "signon": "Sign-on bonus",
           "relocation": "Relocation", "shift_diff": "Shift differential", "vehicle": "Company vehicle", "retention": "Completion bonus"}


def ago(d) -> str:
    if d is None:
        return ""
    return "Today" if d == 0 else ("Yesterday" if d == 1 else (f"{d}d ago" if d < 30 else f"{d // 30}mo ago"))


def perk_labels(j) -> list[str]:
    out = []
    for t in (j.get("perks") or "").split("|"):
        if not t:
            continue
        if t == "per_diem":
            out.append(f'Per diem {money(j["per_diem"]).replace(".00", "")}/day' if j.get("per_diem") else "Per diem")
        elif t.startswith("rotation:"):
            out.append("Rotation " + t.split(":", 1)[1] + " wks")
        elif t.startswith("schedule:"):
            parts = []
            for x in t.split(":", 1)[1].split("/"):
                if x.endswith("hw"):
                    parts.append(x[:-2] + " hrs/wk")
                elif x.endswith("h"):
                    parts.append(x[:-1] + "-hr shifts")
                elif x.endswith("d"):
                    parts.append(x[:-1] + " days/wk")
            out.append("Schedule " + " · ".join(parts))
        else:
            out.append(PERK_EN.get(t, t))
    return out



# Guías locales para ciudades con mucha búsqueda (solo información pública; nunca detalles internos de sitios)
CITY_GUIDES = {
    ("Abilene", "TX"): {
        "intro": ("Abilene is the center of one of the largest AI data center builds in the country: the Stargate campus developed by Crusoe for Oracle and OpenAI, "
                  "with Vantage's Frontier campus rising next door in Shackelford County. That means thousands of construction and technician jobs for several years — "
                  "and most of the cabling, fiber and deployment work is done by contractors who hire fast, pay hourly plus per diem, and run 10–12 hour shifts."),
        "who": [("Who builds here", "General contractors and electrical primes publicly tied to the Abilene campus include DPR, Rosendin, Southland, MMR and Cupertino Electric. "
                                     "Inside-plant cabling and fiber primes posting Abilene jobs include AFL, NTI (Network Connex), Team LINX, Total Deployment Solutions, "
                                     "Black Box and E2 Optics, plus subcontractors and staffing firms such as The Archetype Strategy, Telvero, TEKsystems, Insight Global and Equiliem."),
                ("What the jobs look like", "Structured cabling and fiber technicians (pulling, terminating, ribbon splicing, testing), deployment techs (racks, servers, labeling), "
                                            "cable pullers, foremen and QA/QC. Typical posted pay for techs is $20–$35/hr; foremen and leads $30–$45/hr; splicers up to $40–$44/hr. "
                                            "Contractors that travel crews in often add $100–$180/day per diem and sometimes housing."),
                ("Living and working there", "Abilene is a 2-hour drive west of Fort Worth. Hotels and short-term rentals fill up fast on big project rotations, so ask about housing or per diem before you accept. "
                                            "Shifts of 6×10 or 6×12 are common on the construction side; live-facility technician roles follow 12-hour rotations.")],
        "faq": [("How do I get a job at the Abilene data center?",
                 "Apply directly to the contractors doing the work, not to the owner. Entry-level cabling and deployment techs are hired by contractors and staffing firms listed on this page; "
                 "electricians and HVAC through the electrical and mechanical primes. OSHA 10, a driver's license and the ability to pass a drug test and background check are the usual requirements."),
                ("Do Abilene data center jobs pay per diem?",
                 "Many traveling contractor roles do (typically $100–$180 per day), but most employers don't put it in the posting. Ask the recruiter, and check the jobs tagged with per diem on this site."),
                ("Is there housing?",
                 "Some contractors provide hotel rooms or shared housing for traveling crews; others pay a per diem and leave lodging to you. Local supply is tight during peak construction.")],
    },
}




STATE_GUIDES = {
    "TX": {"intro": "Texas is the busiest data center construction market in the country: the Oracle/OpenAI Stargate campus in Abilene, Vantage Frontier in Shackelford County, "
                    "the OpenAI/SB Energy site in Milam County, Microsoft and Meta in San Antonio and Temple, Google in Midlothian and Red Oak, xAI's suppliers in the Dallas area, "
                    "and hyperscale clusters across DFW, Austin and Houston. No state income tax, right-to-work, and contractors that travel crews in with per diem.",
           "tips": [("Where the jobs cluster", "Abilene (construction, fiber and cabling), Dallas–Fort Worth (Red Oak, Midlothian, Plano, Irving: deployment and operations), San Antonio (Microsoft, operations), Austin/Temple/Round Rock and Houston."),
                    ("Who hires most", "Amazon and Microsoft for operations roles; AFL, NTI, Team LINX, E2 Optics, ADB, TDS, Black Box and Align for cabling and deployment; staffing firms (TEKsystems, Insight Global, Archetype, Telvero) for project crews."),
                    ("What to expect", "Construction-side roles run 6×10 or 6×12 with overtime; per diem of $100–$180/day is common for travelers but rarely posted. Operations roles are 12-hour rotations.")]},
    "VA": {"intro": "Northern Virginia (Ashburn, Sterling, Manassas, Leesburg) is the largest data center market in the world, with hundreds of live facilities and constant expansion, "
                    "plus new campuses in Richmond, Fredericksburg and Virginia Beach. It has the deepest pool of operations jobs — and the most competition for them.",
           "tips": [("Where the jobs cluster", "Loudoun and Prince William counties (Ashburn, Sterling, Manassas, Gainesville), then Richmond/Chester and Hampton Roads."),
                    ("Who hires most", "Amazon, Microsoft, Google, Equinix, QTS and Digital Realty on the operations side; M.C. Dean, Vision Technologies, Align, E2 Optics and TEKsystems-placed crews on construction and cabling."),
                    ("What to expect", "Higher base pay than most states, less per diem (crews are local), strict badging and background checks, 12-hour rotating shifts in live facilities.")]},
    "OH": {"intro": "Central Ohio (New Albany, Columbus, Hilliard, Marysville) is a top-five build market: Google, Amazon, Microsoft and Meta campuses, plus the Lordstown Stargate site in the northeast. "
                    "Cabling and fiber contractors staff New Albany heavily with traveling crews.",
           "tips": [("Where the jobs cluster", "New Albany and Columbus suburbs; Cedar Rapids-style projects to the west; Lordstown/Warren coming."),
                    ("Who hires most", "Google and Amazon for operations; NTI, Telvero, SRI Telecom, Insight Global and TEKsystems for fiber and cabling crews."),
                    ("What to expect", "Fiber splicers with ribbon experience are in demand (Telvero posts $27–$40/hr + $178/day). Winters are real; many crews rotate 3 weeks on / 1 off.")]},
    "AZ": {"intro": "Phoenix–Goodyear–Mesa is one of the fastest-growing data center regions: Microsoft, Google, Meta, Vantage, Aligned, QTS, EdgeCore and many colocation operators. Heat and scale define the work.",
           "tips": [("Where the jobs cluster", "Goodyear and the West Valley (Microsoft), Mesa (Google, Meta, Apple), Chandler and central Phoenix (colocation)."),
                    ("Who hires most", "Microsoft and Amazon for operations; IES Communications, Align, Archetype and staffing firms for cabling and deployment."),
                    ("What to expect", "Year-round construction; summer shifts start early. Arizona requires no low-voltage license for most cabling work, so entry is fast.")]},
}

# Descripciones cortas y neutrales de cada empleador (hechos públicos; sin afirmaciones de pago no publicadas)
COMPANY_BLURBS = {
    "Amazon": "Amazon Web Services runs the largest fleet of data centers in the US and hires Data Center Technicians (DCT L1–L4), Engineering Operations Technicians and Critical Facilities roles directly, with pay posted in every state. Most roles are 12-hour rotating shifts in live facilities.",
    "Google": "Google hires Data Center Technicians and Facilities Technicians directly at its US campuses (Ohio, Texas, Oklahoma, Iowa, Nebraska, Virginia and more). Postings include salary ranges; roles are shift-based with strong benefits.",
    "Microsoft": "Microsoft hires Data Center Technicians and Critical Environment roles for Azure campuses (Texas, Arizona, Virginia, Wisconsin, Iowa…). Much of the build-out cabling is done by contractors; Microsoft's own roles are operations-side.",
    "Oracle": "Oracle Cloud Infrastructure is building fast — Abilene (Stargate), Salt Lake City, Port Washington and Saline among others — and hires data center technicians, low-voltage leads and operations managers directly, while contractors handle most inside-plant cabling.",
    "QTS": "QTS is a hyperscale data center operator (Dallas, Atlanta, Phoenix, Virginia, Texas) hiring Critical Facilities and Data Center Operations technicians for live facilities.",
    "Equinix": "Equinix is the largest colocation operator in the world and hires Data Center Technicians and Critical Facilities Engineers in major US metros; roles are operations-side with structured levels.",
    "xAI": "xAI builds and runs the Colossus AI supercomputer campuses in Memphis/Southaven and hires data center technicians, electricians and construction roles directly, several with per diem and housing noted in the posting.",
    "CoreWeave": "CoreWeave is an AI cloud operator growing data halls across Texas, Virginia, Pennsylvania and more, hiring Data Center Technicians with posted salary ranges.",
    "Network Connex": "National Technologies (NTI), a Network Connex company, is one of the main inside-plant fiber and structured cabling contractors on hyperscale builds (Abilene, Cedar Rapids, Atlanta…), hiring fiber technicians, splicers and data center technicians, many traveling.",
    "AFL": "AFL is a fiber manufacturer and installer that acts as a prime structured-cabling contractor on hyperscale data centers, hiring structured cable technicians, foremen and splicers for projects such as Abilene.",
    "Team LINX": "LINX is a low-voltage contractor (Denver, Salt Lake City, Dallas, El Paso, Cheyenne) hiring low-voltage technicians, leads and foremen for data center construction, with pay by level posted on each role.",
    "E2 Optics": "E2 Optics is a national low-voltage and structured cabling contractor on hyperscale builds, hiring installers, technicians and network specialists in Texas, Utah, Arizona, Virginia and more.",
    "ADB Companies": "ADB is a turnkey infrastructure contractor hiring data center fiber technicians and splicers (Level I–II, traveling) for sites such as Abilene and New Albany.",
    "Black Box": "Black Box is a global infrastructure integrator hiring Infrastructure Technicians and QA roles on data center cabling projects, including Abilene.",
    "Introl": "Introl supplies data center deployment technicians (rack and stack, cabling) to hyperscale and AI sites nationwide; postings list hourly pay and are often project-based.",
    "TDS (Total Deployment Solutions)": "TDS is a deployment contractor hiring Data Center Deployment Technicians (I–II) and cable labeling techs for project work in Texas, Utah and other build markets.",
    "M.C. Dean": "M.C. Dean is a large electrical and mission-critical contractor hiring electricians, technicians and critical-facilities staff on data center construction and operations, mostly in Virginia and the Mid-Atlantic.",
    "The Archetype Strategy": "Archetype Infrastructure Solutions is a labor-support subcontractor supplying data center technicians, cable pullers, redlining techs and fiber splicers to hyperscale projects (Abilene, Dallas, Red Oak, Columbus, Ashburn…). Many roles list hourly pay and per diem.",
    "Telvero": "Telvero is a fiber and inside-plant subcontractor on hyperscale projects (Abilene, Columbus, Bridgeport AL) whose postings state pay, per diem and rotation up front.",
    "SRI Telecom": "SRI Telecom is a Baton Rouge–based fiber and data center contractor with 300+ W-2 technicians, hiring Data Center Technicians (Level I–IV) and ISP technicians nationwide.",
    "Align": "Align is a data center cabling and fit-out contractor hiring Data Center Cabling Foremen and technicians in Sterling, Plano, Phoenix, Detroit, Salt Lake City and other build markets.",
    "Rosendin": "Rosendin is one of the largest electrical contractors in the US and a prime on data center builds (including Abilene), hiring electricians, foremen and field technicians.",
    "Holder Construction": "Holder is a general contractor specializing in mission-critical and data center construction, hiring field engineers and site technicians on projects nationwide.",
    "Vision Technologies": "Vision Technologies is a low-voltage integrator hiring cabling technicians and installers for data center and commercial projects, mainly on the East Coast.",
    "Cologix": "Cologix is a colocation operator (Columbus, Minneapolis, Montreal and more) hiring data center technicians for live facilities.",
    "Nebius": "Nebius builds AI data centers (Kansas City, New Jersey) and hires data center technicians with posted ranges.",
    "Crusoe": "Crusoe develops and operates AI data centers (including the Abilene campus) and hires data center technicians and operations roles.",
    "Compu Dynamics": "Compu Dynamics designs, builds and maintains data centers, hiring critical-facilities technicians mostly in the Mid-Atlantic.",
    "MidPoint Technology Group": "MidPoint Technology Group is a Maryland-based technology integrator (structured cabling, data center, AV, security) working on data center projects including Abilene; it hires through its own board and through subcontractors.",
}


class Site:
    def __init__(self, jobs, out: Path, preview: bool, today: date):
        self.jobs, self.out, self.preview, self.today = jobs, out, preview, today
        self.pages: list[str] = []
        self.survey = {"companies": {}}

    def reported(self, company: str) -> str:
        """Bloque 'Reported by techs' con agregados de la encuesta (solo con 3+ respuestas)."""
        d = (self.survey.get("companies") or {}).get(company)
        if not d:
            return ""
        items = []
        if d.get("pay_median"):
            items.append(f'<li><b>{money(d["pay_median"])}/hr</b><span>median base pay reported</span></li>')
        if d.get("hours_week_median"):
            items.append(f'<li><b>{d["hours_week_median"]} hrs</b><span>typical week</span></li>')
        if d.get("shift"):
            items.append(f'<li><b>{E(d["shift"])}</b><span>most common shift</span></li>')
        if d.get("per_diem"):
            items.append(f'<li><b>{E(d["per_diem"])}</b><span>per diem</span></li>')
        if d.get("housing"):
            items.append(f'<li><b>{E(d["housing"])}</b><span>housing</span></li>')
        if d.get("rotation"):
            items.append(f'<li><b>{E(d["rotation"])}</b><span>rotation</span></li>')
        if d.get("overtime"):
            items.append(f'<li><b>{E(d["overtime"])}</b><span>overtime</span></li>')
        if d.get("again_yes_pct") is not None:
            items.append(f'<li><b>{d["again_yes_pct"]}%</b><span>would work for them again</span></li>')
        return (f'<section class="reported"><h2>Reported by techs <small>({d["n"]} anonymous responses)</small></h2>'
                f'<ul>{"".join(items)}</ul><p class="note">What technicians who worked for {E(company)} told us in the '
                f'<a href="../shift-survey.html">anonymous survey</a>. Shown only with {self.survey.get("min_responses", 3)}+ responses; never individual answers.</p></section>')

    def rel(self, path: str, depth: int) -> str:
        return "../" * depth + path

    @staticmethod
    def breadcrumbs(items) -> str:
        ld = {"@context": "https://schema.org", "@type": "BreadcrumbList",
              "itemListElement": [{"@type": "ListItem", "position": i + 1, "name": n, "item": f"{SITE_URL}/{p}".replace("/index.html", "/")}
                                  for i, (n, p) in enumerate(items)]}
        return f'<script type="application/ld+json">{json.dumps(ld)}</script>'

    @staticmethod
    def org_ld() -> str:
        ld = {"@context": "https://schema.org", "@type": "WebSite", "name": SITE_NAME, "url": SITE_URL,
              "description": SITE_TAGLINE,
              "publisher": {"@type": "Organization", "name": SITE_NAME, "url": SITE_URL,
                            "founder": {"@type": "Person", "name": "Enmanuel V.", "jobTitle": "Inside plant / data center technician"}}}
        return f'<script type="application/ld+json">{json.dumps(ld)}</script>'

    def page(self, path: str, title: str, desc: str, body: str, canonical: bool = True, head_extra: str = ""):
        depth = path.count("/")
        r = lambda p: self.rel(p, depth)  # noqa: E731
        nav = (f'<nav class="main" aria-label="Main"><a href="{r("index.html")}">Jobs</a>'
               f'<a href="{r("new-jobs.html")}">New</a><a href="{r("entry-level-jobs.html")}">Entry level</a>'
               f'<a href="{r("salaries.html")}">Salaries</a><a href="{r("companies.html")}">Companies</a>'
               f'<a href="{r("states.html")}">States</a><a href="{r("certifications.html")}">Certifications</a>'
               f'<a href="{r("travel-jobs.html")}">Per diem</a>'
               f'<a href="{r("shift-schedules.html")}">Shifts</a>'
               f'<a href="{r("about.html")}">About</a></nav>')
        url = f"{SITE_URL}/{path}".replace("/index.html", "/")
        bare = self.preview and path == "index.html"
        doc_head = ("" if bare else "<!doctype html><html lang=\"en\"><head><meta charset=\"utf-8\">"
                    "<meta name=\"viewport\" content=\"width=device-width,initial-scale=1,viewport-fit=cover\">")
        h = (f"{doc_head}<title>{E(title)}</title>"
             f'<meta name="claude:viewport-fit-sides" content="cover">'
             f'<meta name="description" content="{E(desc)}">'
             + (f'<link rel="canonical" href="{E(url)}">' if canonical and not self.preview else "")
             + f'<meta property="og:title" content="{E(title)}"><meta property="og:description" content="{E(desc)}">'
             + f'<link rel="icon" href="{r("favicon.svg")}" type="image/svg+xml"><link rel="apple-touch-icon" href="{r("apple-touch-icon.png")}">'
             + f'<meta property="og:image" content="{SITE_URL}/og.png"><meta name="twitter:card" content="summary_large_image">'
             + f'<link rel="alternate" type="application/rss+xml" title="New data center jobs" href="{r("feed.xml")}">'
             + FONTS + f"<style>{CSS}</style>{head_extra}"
             + ("" if bare else "</head><body>")
             + f'<header class="site"><div class="wrap"><a class="brand" href="{r("index.html")}"><i aria-hidden="true"></i>Data Center <em>Job USA</em></a>{nav}</div></header>'
             + (f'<main>{body}</main>' if body.startswith('<section class="hero">') else f'<main><div class="wrap">{body}</div></main>')
             + f'<footer class="site"><div class="wrap"><div class="cols">'
             + f'<div><b>{E(SITE_NAME)}</b><p>{E(SITE_TAGLINE)}. Built and run by a working data center technician in Texas. '
               f'Every listing links to the employer\'s own career page; we never collect applications.</p>'
               f'<p class="upd">Last updated {self.today:%B %-d, %Y} · refreshed every morning</p></div>'
             + f'<div><b>Find jobs</b><a href="{r("index.html")}">All technician jobs</a><a href="{r("entry-level-jobs.html")}">Entry-level jobs</a>'
               f'<a href="{r("travel-jobs.html")}">Per diem &amp; housing</a><a href="{r("states.html")}">Jobs by state</a><a href="{r("companies.html")}">Jobs by company</a></div>'
             + f'<div><b>Pay &amp; career</b><a href="{r("salaries.html")}">Technician salaries</a><a href="{r("shift-schedules.html")}">Shift schedules</a>'
               f'<a href="{r("certifications.html")}">Certifications</a><a href="{r("how-to-become-a-data-center-technician.html")}">How to become a tech</a><a href="{r("shift-survey.html")}">Tech survey</a></div>'
             + f'<div><b>About</b><a href="{r("about.html")}">Who runs this site</a><a href="{r("about.html")}#data">Where the data comes from</a>'
               f'<a href="{r("shift-survey.html")}">Send feedback</a></div>'
             + '</div></div></footer>'
             + ("" if bare else "</body></html>"))
        f = self.out / path
        f.parent.mkdir(parents=True, exist_ok=True)
        f.write_text(h, encoding="utf-8")
        self.pages.append(path)

    # -------------------------------------------------------------- pieces
    @staticmethod
    def perk_chips(j) -> str:
        return "".join(f'<span class="chip perk">{E(t)}</span>' for t in perk_labels(j))

    def job_row(self, j, depth: int, scale_max: float) -> str:
        title = clean_title(j["title"])
        loc = f'{j["city"]}, {j["state"]}' if j["city"] else STATE_NAMES.get(j["state"], j["state"])
        href = (self.rel(f'jobs/{j["slug"]}.html', depth) if not self.preview else j["url"])
        ext = "" if not self.preview else ' rel="noopener" target="_blank"'
        chips = f'<span class="chip">{E(ROLE_EN.get(j["role"], j["role"]))}</span>'
        if j.get("level"):
            chips += f' <span class="chip lvl">Level {E(j["level"])}</span>'
        if j["openings"] > 1:
            chips += f' <span class="chip">{j["openings"]} openings</span>'
        if j.get("days_posted") is not None and j["days_posted"] <= 7:
            chips += ' <span class="chip new">New</span>'
        if j.get("entry"):
            chips += ' <span class="chip entry">Entry level</span>'
        chips += self.perk_chips(j)
        age = ago(j.get("days_posted"))
        if j["hourly_min"]:
            lo, hi = j["hourly_min"], j["hourly_max"] or j["hourly_min"]
            pay = (f'<div class="pay">{money(lo)}–{money(hi)}<small>per hour'
                   + (f' · {money(j["pay_min"], "year")}–{money(j["pay_max"], "year")}/yr' if j["pay_unit"] == "year" else "")
                   + '</small></div>')
        else:
            pay = '<div class="pay nopay">Pay not posted<small>ask the recruiter</small></div>'
        return (f'<li class="job">{logo(j["company"])}<div><a class="t" href="{E(href)}"{ext}>{E(title)}</a>'
                f'<div class="meta"><span class="co">{E(j["company"])}</span><span>{E(loc)}</span>{f"<span class=age>{age}</span>" if age else ""}</div>'
                f'<div class="tags">{chips}</div></div>{pay}</li>')

    def job_list(self, rows, depth: int, limit: int | None = None) -> str:
        scale = max([j["hourly_max"] or 0 for j in self.jobs] + [1])
        rows = sorted(rows, key=lambda j: (-(j["hourly_max"] or 0)))
        shown = rows if limit is None else rows[:limit]
        return '<ul class="jobs">' + "".join(self.job_row(j, depth, scale) for j in shown) + "</ul>"

    def pay_table(self, rows, group_key, label, depth, link=None) -> str:
        groups = defaultdict(list)
        for j in rows:
            groups[group_key(j)].append(j)
        body = []
        for k, js in sorted(groups.items(), key=lambda kv: -sum(j["openings"] for j in kv[1])):
            paid = [j for j in js if j["hourly_min"]]
            n = sum(j["openings"] for j in js)
            lo = statistics.median([j["hourly_min"] for j in paid]) if paid else None
            hi = statistics.median([j["hourly_max"] for j in paid]) if paid else None
            name = E(k) if not link else f'<a href="{E(self.rel(link(k), depth))}">{E(k)}</a>'
            body.append(f"<tr><td>{name}</td><td class=num>{n}</td><td class=num>{money(lo)}</td>"
                        f"<td class=num>{money(hi)}</td><td class=num>{len(paid)}/{len(js)}</td></tr>")
        return ('<div class="tablebox"><table><thead><tr>'
                f"<th>{E(label)}</th><th>Openings</th><th>Typical low $/hr</th><th>Typical high $/hr</th><th>Postings with pay</th>"
                "</tr></thead><tbody>" + "".join(body) + "</tbody></table></div>")

    def signup(self) -> str:
        return ('<div class="callout"><h3>Get the best new jobs every Monday</h3>'
                '<p class="note">One email a week: the highest-paying new technician openings and one real number about pay or shifts. No spam, no recruiters.</p>'
                f'<form class="signup" action="{E(NEWSLETTER_ACTION)}" method="post" target="_blank" '
                'onsubmit="const f=this;fetch(f.action,{method:\'POST\',mode:\'no-cors\',body:new FormData(f)}).then(()=>{f.innerHTML=\'<p class=ok>Check your inbox and confirm your email. Welcome aboard.</p>\'});event.preventDefault();">'
                '<label for="nl-email" class="note" style="flex-basis:100%">Email</label>'
                '<input id="nl-email" name="email" type="email" required placeholder="you@example.com" autocomplete="email">'
                '<input type="hidden" name="tag" value="site">'
                '<button type="submit">Join the weekly list</button></form></div>')

    # -------------------------------------------------------------- pages
    def build(self):
        js = self.jobs
        total = sum(j["openings"] for j in js)
        paid = sum(j["openings"] for j in js if j["hourly_min"])
        companies = Counter()
        for j in js:
            companies[j["company"]] += j["openings"]
        states = Counter()
        for j in js:
            states[j["state"]] += j["openings"]

        # ---- index with client-side filters
        data = [{"t": clean_title(j["title"]), "c": j["company"], "ci": j["city"], "s": j["state"],
                 "r": ROLE_EN.get(j["role"], j["role"]), "n": j["openings"], "lo": j["hourly_min"],
                 "hi": j["hourly_max"], "d": j["days_posted"], "p": perk_labels(j), "e": 1 if j.get("entry") else 0, "l": j.get("level") or "",
                 "yr": [j["pay_min"], j["pay_max"]] if j["pay_unit"] == "year" and j["pay_min"] else None,
                 "u": (f'jobs/{j["slug"]}.html' if not self.preview else j["url"])} for j in js]
        opts = lambda vals: "".join(f'<option value="{E(v)}">{E(v)}</option>' for v in vals)  # noqa: E731
        scale = max([j["hourly_max"] or 0 for j in js] + [1])
        top_states = [(STATE_NAMES.get(st, st), f"states/{slug(STATE_NAMES.get(st, st))}.html") for st, _ in states.most_common(4)]
        quick = ('<a href="new-jobs.html">New this week</a><a href="entry-level-jobs.html">Entry level / no experience</a><a href="travel-jobs.html">Per diem &amp; housing</a><a href="how-to-become-a-data-center-technician.html">How to get in</a><a href="salaries.html">Compare pay</a><a href="shift-schedules.html">Shift schedules</a><a href="shift-survey.html">Tech survey</a>')
        fresh_n = sum(j["openings"] for j in js if j.get("days_posted") is not None and j["days_posted"] <= 7)
        entry_n = sum(j["openings"] for j in js if j.get("entry"))
        perk_n = sum(j["openings"] for j in js if j.get("perks") and re.search(r"per_diem|housing", j["perks"]))
        top_states_snap = "".join(f'<a href="{E(u)}">{E(n)}</a>' for n, u in top_states)
        body = ('<section class="hero"><div class="wrap"><div class="grid"><div>'
                '<p class="kicker">Built by a working data center tech · Updated every morning</p>'
                '<h1>Data center technician jobs with the <mark>pay up front</mark>.</h1>'
                f'<p class="lede">{total:,} open jobs at {len(companies)} operators and contractors, read straight from their own career pages. '
                f'{paid / total:.0%} show the pay range. No agencies, no résumé harvesting.</p>'
                '<form class="search" onsubmit="event.preventDefault();const q=document.getElementById(\'q\'),st=document.getElementById(\'st\');q.value=this.s.value;st.value=this.st.value;q.dispatchEvent(new Event(\'input\'));document.getElementById(\'f\').scrollIntoView({behavior:\'smooth\'})">'
                '<input name="s" type="search" placeholder="Job title, keyword or city — fiber, electrician, Abilene…" aria-label="Search jobs">'
                f'<select name="st" aria-label="State"><option value="">All states</option>{"".join(f"<option value=\"{E(st)}\">{E(STATE_NAMES.get(st, st))}</option>" for st, _ in states.most_common())}</select>'
                '<button type="submit">Find jobs</button></form>'
                f'<div class="quick">{quick}</div></div>'
                '<aside class="snap"><h2>Today on the site</h2><ul>'
                f'<li><a href="index.html"><b>{total:,}</b><span>open technician jobs</span></a></li>'
                f'<li><a href="new-jobs.html"><b>{fresh_n:,}</b><span>posted this week</span></a></li>'
                f'<li><a href="entry-level-jobs.html"><b>{entry_n:,}</b><span>entry level / no experience</span></a></li>'
                f'<li><a href="travel-jobs.html"><b>{perk_n:,}</b><span>mention per diem or housing</span></a></li></ul>'
                f'<p class="top">Most jobs: {top_states_snap}</p></aside>'
                f'<p class="live"><a href="new-jobs.html"><b>{fresh_n:,}</b> posted this week</a><a href="entry-level-jobs.html"><b>{entry_n:,}</b> entry level</a>'
                f'<a href="travel-jobs.html"><b>{perk_n:,}</b> mention per diem or housing</a><span><b>{len(companies)}</b> employers</span><span>Updated {self.today:%b %-d}</span></p>'
                '</div></div></section><div class="wrap">'
                f'<div class="stats"><div class="stat"><b>{self.today:%b %-d}</b><span>last updated · daily</span></div>'
                f'<div class="stat"><b>{len(companies)}</b><span>employers tracked</span></div>'
                f'<div class="stat"><b>{len(states)}</b><span>states</span></div>'
                f'<div class="stat"><b>{paid / total:.0%}</b><span>with pay posted</span></div></div>'
                '<section class="browse" id="browse"><div><h2>By type of work</h2><div class="quick">'
                + "".join(f'<a href="roles/{slug(r)}.html">{E(r)} <small>{n:,}</small></a>' for r, n in Counter({ROLE_EN.get(j["role"], j["role"]): 0 for j in js}).items() for n in [sum(x["openings"] for x in js if ROLE_EN.get(x["role"], x["role"]) == r)])
                + '</div></div><div><h2>By level</h2><div class="quick">'
                + "".join(f'<a href="levels/{slug(l)}.html">{E(n)} <small>{sum(x["openings"] for x in js if x.get("level") == l):,}</small></a>'
                          for l, n in [("I", "Level I / entry"), ("II", "Level II"), ("III", "Level III / senior"), ("IV", "Level IV")] if any(x.get("level") == l for x in js))
                + '<a href="entry-level-jobs.html">No experience <small>guide</small></a></div></div></section>'
                '<form class="filters" id="f" onsubmit="event.preventDefault()">'
                '<label for="q">Search<input id="q" type="search" placeholder="Title or city"></label>'
                f'<label for="st">State<select id="st"><option value="">All states</option>{opts(sorted(states))}</select></label>'
                f'<label for="co">Company<select id="co"><option value="">All companies</option>{opts(sorted(companies))}</select></label>'
                f'<label for="ro">Type<select id="ro"><option value="">All types</option>{opts(sorted({d["r"] for d in data}))}</select></label>'
                '<label for="pay">Min $/hr<input id="pay" type="number" min="0" step="1" placeholder="e.g. 35"></label>'
                '<label for="lv">Level<select id="lv"><option value="">Any level</option><option value="I">Level I</option><option value="II">Level II</option><option value="III">Level III / senior</option><option value="IV">Level IV</option></select></label>'
                '<label for="ex">Experience<select id="ex"><option value="">Any</option><option value="1">Entry level / no experience</option></select></label>'
                '<label for="pk">Perks<select id="pk"><option value="">Any</option><option value="Per diem">Per diem</option><option value="Housing">Housing / lodging</option>'
                '<option value="Travel">Travel job</option><option value="Schedule">Schedule stated (12s, 6 days…)</option><option value="Overtime">Overtime</option><option value="Sign-on bonus">Sign-on bonus</option></select></label>'
                '<label for="so">Sort<select id="so"><option value="pay">Highest pay</option><option value="new">Newest</option></select></label>'
                '</form><p class="count" id="cnt" aria-live="polite"></p><ul class="jobs" id="list"></ul>'
                '<button class="more" id="more" type="button">Show more jobs</button>'
                '<section class="how"><h2>How this site works</h2><ol>'
                '<li><b>We read the source.</b> Every morning the site reads the career pages of data center operators (Amazon, Google, Microsoft, QTS…) and the contractors who build and cable them (NTI, AFL, LINX, E2 Optics, ADB…).</li>'
                '<li><b>We keep only technician work.</b> Data center techs, critical facilities, electricians, fiber and structured cabling, deployment. No sales, no managers, no fake "data entry" listings.</li>'
                '<li><b>We put the pay first.</b> Hourly and salaried ranges are converted to $/hr so you can compare, and we flag per diem, housing and schedules when the employer states them.</li>'
                '<li><b>You apply with the employer.</b> Every button goes to the company\'s own site. We never see your application.</li></ol></section>'
                + self.signup()
                + f'<script>const J={json.dumps(data, separators=(",", ":"))};const SC={scale};const LG={json.dumps({c: logo(c) for c in companies})};const ST={json.dumps({s: STATE_NAMES.get(s, s) for s in states})};'
                + r"""
const $=id=>document.getElementById(id);let N=40;
const esc=s=>String(s).replace(/[&<>"]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]));
const m=v=>'$'+v.toFixed(2);
const ago=d=>d==null?'':(d===0?'Today':d===1?'Yesterday':d<30?d+'d ago':Math.floor(d/30)+'mo ago');
const yr=v=>'$'+Math.round(v).toLocaleString();
function row(j){let pay='<div class="pay nopay">Pay not posted<small>ask the recruiter</small></div>';
 if(j.lo){pay=`<div class="pay">${m(j.lo)}–${m(j.hi)}<small>per hour${j.yr?' · '+yr(j.yr[0])+'–'+yr(j.yr[1])+'/yr':''}</small></div>`}
 const ext=/^https?:/.test(j.u)?' rel="noopener" target="_blank"':'';
 const a=ago(j.d);
 return `<li class="job">${LG[j.c]||''}<div><a class="t" href="${esc(j.u)}"${ext}>${esc(j.t)}</a><div class="meta"><span class="co">${esc(j.c)}</span><span>${j.ci?esc(j.ci)+', '+j.s:esc(ST[j.s]||j.s)}</span>${a?`<span class="age">${a}</span>`:''}</div><div class="tags"><span class="chip">${esc(j.r)}</span>${j.l?`<span class="chip lvl">Level ${j.l}</span>`:''}${j.n>1?`<span class="chip">${j.n} openings</span>`:''}${j.d!==null&&j.d<=7?'<span class="chip new">New</span>':''}${j.e?'<span class="chip entry">Entry level</span>':''}${(j.p||[]).map(t=>`<span class="chip perk">${esc(t)}</span>`).join('')}</div></div>${pay}</li>`}
function draw(){const q=$('q').value.trim().toLowerCase(),st=$('st').value,co=$('co').value,ro=$('ro').value,p=parseFloat($('pay').value)||0,so=$('so').value,pk=$('pk').value,ex=$('ex').value,lv=$('lv').value;
 let r=J.filter(j=>(!q||(j.t+' '+j.ci).toLowerCase().includes(q))&&(!st||j.s===st)&&(!co||j.c===co)&&(!ro||j.r===ro)&&(!p||(j.hi||0)>=p)&&(!pk||(j.p||[]).some(t=>t.startsWith(pk)))&&(!ex||j.e)&&(!lv||j.l===lv));
 r.sort(so==='new'?(a,b)=>(a.d??999)-(b.d??999):(a,b)=>(b.hi||0)-(a.hi||0));
 const n=r.reduce((s,j)=>s+j.n,0);$('cnt').textContent=`${n.toLocaleString()} openings in ${r.length.toLocaleString()} listings`;
 $('list').innerHTML=r.slice(0,N).map(row).join('');$('more').hidden=r.length<=N}
['q','st','co','ro','pay','lv','ex','pk','so'].forEach(id=>$(id).addEventListener('input',()=>{N=40;draw()}));
$('more').addEventListener('click',()=>{N+=40;draw()});draw();
</script></div>""")
        self.page("index.html", SITE_NAME if self.preview else f"Data Center Technician Jobs with Pay, Updated Daily | {SITE_NAME}",
                  f"{total:,} data center jobs for technicians, electricians and fiber techs at {len(companies)} employers, with posted pay ranges. "
                  f"Filter by state, company, entry level and per diem. Updated {self.today:%B %-d, %Y}.", body, head_extra=self.org_ld())

        # ---- salaries
        paid_js = [j for j in js if j["hourly_min"]]
        med = lambda rows, k: statistics.median([j[k] for j in rows]) if rows else None  # noqa: E731
        all_lo, all_hi = med(paid_js, "hourly_min"), med(paid_js, "hourly_max")
        dct = [j for j in paid_js if ROLE_EN.get(j["role"], j["role"]) == "Data center technician"]
        lvl_rows = []
        for lv, name in [("I", "Level I / entry"), ("II", "Level II"), ("III", "Level III / senior"), ("IV", "Level IV")]:
            r = [j for j in paid_js if j.get("level") == lv]
            if len(r) >= 3:
                lvl_rows.append(f'<tr><td><a href="levels/{slug(lv)}.html">{E(name)}</a></td><td class=num>{sum(j["openings"] for j in r)}</td>'
                                f'<td class=num>{money(med(r, "hourly_min"))}</td><td class=num>{money(med(r, "hourly_max"))}</td><td class=num>{len(r)}</td></tr>')
        # ranking de empleadores para el puesto de técnico de data center
        by_co = defaultdict(list)
        for j in dct:
            by_co[j["company"]].append(j)
        rank = sorted(((c, med(r, "hourly_max"), med(r, "hourly_min"), len(r)) for c, r in by_co.items() if len(r) >= 2), key=lambda t: -t[1])
        rank_rows = "".join(f'<tr><td>{i + 1}</td><td><a href="companies/{slug(c)}.html">{E(c)}</a></td><td class=num>{money(lo)}</td><td class=num>{money(hi)}</td><td class=num>{n}</td></tr>'
                            for i, (c, hi, lo, n) in enumerate(rank[:15]))
        perk_pd = [j for j in js if j.get("per_diem")]
        faq = [
            ("How much does a data center technician make?",
             f"Across {len(paid_js):,} technician postings with pay on this site, the typical employer-posted range is {money(all_lo)}–{money(all_hi)} per hour "
             f"(about {money(all_lo * 2080, 'year')}–{money(all_hi * 2080, 'year')} a year at 40 hours). Entry-level roles post around the low end; Level III, leads and critical-facilities roles post the high end. "
             "These are the ranges employers publish, not self-reported salaries."),
            ("Which companies pay data center technicians the most?",
             ("The highest posted ranges for data center technician roles right now come from " + ", ".join(c for c, *_ in rank[:3]) + ". " if len(rank) >= 3 else "")
             + "Hyperscalers and operators tend to post higher base ranges; contractors post lower hourly rates but add overtime and per diem, which often make the weekly check bigger."),
            ("Do data center technicians get overtime and per diem?",
             "On construction and deployment projects, yes: 50–72 hour weeks are common and overtime is paid after 40 hours. Traveling contractors usually add per diem of $100–$180 a day, "
             "though most postings don't state it. Operations roles at hyperscalers are usually salaried or hourly with shift differentials."),
            ("How is pay converted to hourly on this site?",
             "Salaried ranges are divided by 2,080 hours (40 hours × 52 weeks). We use only the range the employer wrote in the posting; we never estimate. 'Typical' is the median of the posted minimums and maximums."),
        ]
        faq_html = "".join(f'<details><summary>{E(q)}</summary><p>{E(a)}</p></details>' for q, a in faq)
        faq_ld = {"@context": "https://schema.org", "@type": "FAQPage",
                  "mainEntity": [{"@type": "Question", "name": q, "acceptedAnswer": {"@type": "Answer", "text": a}} for q, a in faq]}
        body = ('<p class="crumbs"><a href="index.html">Jobs</a> / Salaries</p>'
                f'<h1>Data center technician salary in {self.today.year}: what employers actually post</h1>'
                f'<p class="lede">Typical posted range across {len(paid_js):,} technician jobs with pay: <b>{money(all_lo)}–{money(all_hi)} per hour</b> '
                f'({money(all_lo * 2080, "year")}–{money(all_hi * 2080, "year")} a year at 40 hours). Every number here comes from the employer\'s own posting, converted to $/hr so salaried and hourly jobs line up. '
                'No self-reported guesses, no estimates.</p>'
                f'<div class="stats"><div class="stat"><b>{money(all_lo)}</b><span>typical low $/hr</span></div><div class="stat"><b>{money(all_hi)}</b><span>typical high $/hr</span></div>'
                f'<div class="stat"><b>{len(paid_js):,}</b><span>postings with pay</span></div><div class="stat"><b>{len(perk_pd)}</b><span>state a per diem amount</span></div></div>'
                '<h2>By level</h2><div class="tablebox"><table><thead><tr><th>Level</th><th>Openings</th><th>Typical low $/hr</th><th>Typical high $/hr</th><th>Postings with pay</th></tr></thead>'
                f'<tbody>{"".join(lvl_rows)}</tbody></table></div>'
                '<h2>Highest-paying employers for "Data center technician" roles</h2>'
                '<p class="note">Employers with at least two data center technician postings that include pay, ranked by the typical high end of their range.</p>'
                '<div class="tablebox"><table><thead><tr><th>#</th><th>Employer</th><th>Typical low $/hr</th><th>Typical high $/hr</th><th>Postings</th></tr></thead>'
                f'<tbody>{rank_rows}</tbody></table></div>'
                '<h2>By employer (all technician roles)</h2>' + self.pay_table(js, lambda j: j["company"], "Employer", 0, lambda k: f"companies/{slug(k)}.html")
                + '<h2>By job type</h2>' + self.pay_table(js, lambda j: ROLE_EN.get(j["role"], j["role"]), "Job type", 0, lambda k: f"roles/{slug(k)}.html")
                + '<h2>By state</h2>' + self.pay_table(js, lambda j: STATE_NAMES.get(j["state"], j["state"]), "State", 0,
                                                      lambda k: f"states/{slug(k)}.html")
                + '<h2>Questions people ask</h2><div class="faq">' + faq_html + '</div>'
                + '<p class="note">Salaried ranges are divided by 2,080 hours. Pay ranges are the employer\'s posted range for the role, not what any one person earns. '
                  'Amazon, Google and Microsoft post pay in every state; some employers only post it where state law requires. Per diem, housing and overtime are tagged on the '
                  '<a href="travel-jobs.html">per diem &amp; housing</a> page.</p>'
                + self.signup())
        self.page("salaries.html", f"Data Center Technician Salary {self.today.year}: Pay by Level, Company and State | {SITE_NAME}",
                  f"How much data center technicians make in {self.today.year}: {money(all_lo)}–{money(all_hi)}/hr typical, from {len(paid_js):,} employer-posted ranges at {len(companies)} employers, "
                  "by level, company, job type and state. No estimates.", body, head_extra=f'<script type="application/ld+json">{json.dumps(faq_ld)}</script>')

        city_counts_all = Counter()
        for j in js:
            city_counts_all[(j["city"], j["state"])] += j["openings"]
        city_pages_set = {k for k, v in city_counts_all.items() if v >= MIN_CITY_OPENINGS and k[0]}

        # ---- companies
        links = "".join(f'<li><a href="companies/{slug(c)}.html">{logo(c)}<span>{E(c)}</span><small>{n:,}</small></a></li>'
                        for c, n in companies.most_common())
        self.page("companies.html", f"Data Center Companies Hiring Technicians | {SITE_NAME}",
                  "Data center operators hiring technicians now, with open jobs and pay.",
                  '<p class="crumbs"><a href="index.html">Jobs</a> / Companies</p><h1>Who is hiring technicians</h1>'
                  f'<ul class="grid-links">{links}</ul>')
        for c, n in companies.items():
            rows = [j for j in js if j["company"] == c]
            cs = Counter()
            for j in rows:
                cs[j["state"]] += j["openings"]
            st_links = "".join(f'<li><a href="../states/{slug(STATE_NAMES.get(s, s))}.html"><span>{E(STATE_NAMES.get(s, s))}</span><small>{k}</small></a></li>'
                               for s, k in cs.most_common())
            cpaid = [j for j in rows if j["hourly_min"]]
            c_lo = statistics.median([j["hourly_min"] for j in cpaid]) if cpaid else None
            c_hi = statistics.median([j["hourly_max"] for j in cpaid]) if cpaid else None
            fresh_c = sum(j["openings"] for j in rows if j.get("days_posted") is not None and j["days_posted"] <= 7)
            entry_c = sum(j["openings"] for j in rows if j.get("entry"))
            perk_c = sorted({t for j in rows for t in perk_labels(j)})
            lv_c = Counter(j["level"] for j in rows if j.get("level"))
            city_c = Counter()
            for j in rows:
                if j["city"]:
                    city_c[(j["city"], j["state"])] += j["openings"]
            city_links = "".join((f'<li><a href="../cities/{slug(ci + "-" + st)}.html"><span>{E(ci)}, {st}</span><small>{k}</small></a></li>'
                                  if (ci, st) in city_pages_set else f'<li><a href="#jobs"><span>{E(ci)}, {st}</span><small>{k}</small></a></li>')
                                 for (ci, st), k in city_c.most_common(12))
            cfaq = [(f"How many data center technician jobs does {c} have open?",
                     f"{n:,} technician openings as of {self.today:%B %-d, %Y}, in {len(cs)} states, read directly from {c}'s career page. {fresh_c} were posted in the last 7 days."),
                    (f"How much does {c} pay data center technicians?",
                     (f"{c}'s posted ranges for technician roles run {money(c_lo)}–{money(c_hi)} per hour (typical), by job type: see the table above. " if c_lo else f"{c} does not post pay ranges on most technician listings; ask the recruiter. ")
                     + (f"Postings mention: {', '.join(perk_c)}." if perk_c else "No per diem, housing or schedule details are stated in current postings.")),
                    (f"Does {c} hire entry-level data center technicians?",
                     f"Yes — {entry_c} current openings are tagged entry level (Level I / no experience required)." if entry_c else f"Not in the current postings; check the entry-level page for employers hiring Level I techs now.")]
            cfaq_html = "".join(f'<details><summary>{E(q)}</summary><p>{E(a)}</p></details>' for q, a in cfaq)
            cfaq_ld = '<script type="application/ld+json">' + json.dumps({"@context": "https://schema.org", "@type": "FAQPage",
                      "mainEntity": [{"@type": "Question", "name": q, "acceptedAnswer": {"@type": "Answer", "text": a}} for q, a in cfaq]}) + '</script>'
            body = (f'<p class="crumbs"><a href="../index.html">Jobs</a> / <a href="../companies.html">Companies</a> / {E(c)}</p>'
                    f'<h1>{logo(c)} {E(c)} data center jobs</h1>'
                    f'<p class="lede">{n:,} open technician jobs at {E(c)} across {len(cs)} states, read from its career page this morning. '
                    + (f'Typical posted pay: <b>{money(c_lo)}–{money(c_hi)}/hr</b>. ' if c_lo else 'Pay is not posted on most listings. ')
                    + (f'{fresh_c} new this week. ' if fresh_c else '') + (f'{entry_c} entry level.' if entry_c else '') + '</p>'
                    + (f'<div class="guide"><h2>About {E(c)}</h2><div class="prose"><p>{E(COMPANY_BLURBS[c])}</p></div></div>' if c in COMPANY_BLURBS else '')
                    + f'<div class="stats"><div class="stat"><b>{n:,}</b><span>open jobs</span></div><div class="stat"><b>{fresh_c}</b><span>new this week</span></div>'
                      f'<div class="stat"><b>{len(cpaid)}/{len(rows)}</b><span>postings with pay</span></div><div class="stat"><b>{entry_c}</b><span>entry level</span></div></div>'
                    + self.reported(c)
                    + '<h2>Pay by job type</h2>' + self.pay_table(rows, lambda j: ROLE_EN.get(j["role"], j["role"]), "Job type", 1, lambda k: f"roles/{slug(k)}.html")
                    + (('<h2>By level</h2><div class="quick">' + "".join(f'<a href="../levels/{slug(l)}.html">Level {E(l)} <small>{k}</small></a>' for l, k in sorted(lv_c.items())) + '</div>') if lv_c else '')
                    + '<h2>Where they are hiring</h2>' + f'<ul class="grid-links">{st_links}</ul>'
                    + (f'<h3>Cities</h3><ul class="grid-links">{city_links}</ul>' if city_links else '')
                    + (f'<h2>Perks mentioned in postings</h2><div class="tags">' + "".join(f'<span class="chip perk">{E(t)}</span>' for t in perk_c) + '</div>' if perk_c else '')
                    + '<h2 id="jobs">Open jobs</h2>' + self.job_list(rows, 1)
                    + '<h2>Questions people ask</h2><div class="faq">' + cfaq_html + '</div>' + self.signup())
            self.page(f"companies/{slug(c)}.html", f"{c} Data Center Jobs: {n:,} Open Technician Roles and Pay | {SITE_NAME}",
                      f"{n:,} open {c} data center technician jobs in {len(cs)} states, with posted pay ranges by job type. Updated {self.today:%B %-d, %Y}.", body,
                      head_extra=self.breadcrumbs([("Jobs", "index.html"), ("Companies", "companies.html"), (c, f"companies/{slug(c)}.html")]) + cfaq_ld)

        # ---- states and cities
        links = "".join(f'<li><a href="states/{slug(STATE_NAMES.get(s, s))}.html"><span>{E(STATE_NAMES.get(s, s))}</span><small>{n:,}</small></a></li>'
                        for s, n in states.most_common())
        self.page("states.html", f"Data Center Technician Jobs by State | {SITE_NAME}",
                  "Data center technician jobs and pay in every state with openings.",
                  '<p class="crumbs"><a href="index.html">Jobs</a> / States</p><h1>Jobs by state</h1>'
                  f'<ul class="grid-links">{links}</ul>')
        city_counts = Counter()
        for j in js:
            city_counts[(j["city"], j["state"])] += j["openings"]
        city_pages = {k for k, v in city_counts.items() if v >= MIN_CITY_OPENINGS and k[0]}  # sin ciudad = sin página
        for s, n in states.items():
            name = STATE_NAMES.get(s, s)
            rows = [j for j in js if j["state"] == s]
            cities = Counter()
            for j in rows:
                cities[j["city"]] += j["openings"]
            c_links = "".join(
                (f'<li><a href="../cities/{slug(ci + "-" + s)}.html"><span>{E(ci)}</span><small>{k}</small></a></li>'
                 if (ci, s) in city_pages else f'<li><a href="#jobs"><span>{E(ci or "Statewide / unspecified")}</span><small>{k}</small></a></li>')
                for ci, k in cities.most_common())
            sg = STATE_GUIDES.get(s)
            sguide = (('<section class="guide"><h2>Working in ' + E(name) + '</h2><div class="prose"><p>' + E(sg["intro"]) + '</p>'
                       + "".join(f'<p><b>{E(h)}.</b> {E(t)}</p>' for h, t in sg["tips"]) + '</div></section>') if sg else '')
            spaid = [j for j in rows if j["hourly_min"]]
            body = (f'<p class="crumbs"><a href="../index.html">Jobs</a> / <a href="../states.html">States</a> / {E(name)}</p>'
                    f'<h1>Data center technician jobs in {E(name)}</h1>'
                    f'<p class="lede">{n:,} open technician jobs in {len(cities)} {"city" if len(cities) == 1 else "cities"} from {len({j["company"] for j in rows})} employers. '
                    + (f'Typical posted pay: <b>{money(statistics.median([j["hourly_min"] for j in spaid]))}–{money(statistics.median([j["hourly_max"] for j in spaid]))}/hr</b>. ' if spaid else '')
                    + f'{sum(j["openings"] for j in rows if j.get("entry"))} entry level · {sum(j["openings"] for j in rows if j.get("days_posted") is not None and j["days_posted"] <= 7)} new this week.</p>'
                    + sguide
                    + '<h2>Pay by employer</h2>' + self.pay_table(rows, lambda j: j["company"], "Employer", 1, lambda k: f"companies/{slug(k)}.html")
                    + '<h2>Cities</h2>' + f'<ul class="grid-links">{c_links}</ul>'
                    + '<h2 id="jobs">Open jobs</h2>' + self.job_list(rows, 1) + self.signup())
            self.page(f"states/{slug(name)}.html", f"Data Center Jobs in {name}: {n:,} Technician Openings with Pay | {SITE_NAME}",
                      f"{n:,} data center technician jobs in {name} across {len(cities)} cities, with posted pay by employer. Updated {self.today:%B %-d, %Y}.", body,
                      head_extra=self.breadcrumbs([("Jobs", "index.html"), ("States", "states.html"), (name, f"states/{slug(name)}.html")]))
        for (ci, s) in city_pages:
            rows = [j for j in js if j["city"] == ci and j["state"] == s]
            n = city_counts[(ci, s)]
            name = STATE_NAMES.get(s, s)
            g = CITY_GUIDES.get((ci, s))
            guide_html = ""
            faq_ld = ""
            if g:
                guide_html = ('<section class="guide"><h2>Working in ' + E(ci) + '</h2><div class="prose"><p>' + E(g["intro"]) + '</p>'
                              + "".join(f'<p><b>{E(h)}.</b> {E(t)}</p>' for h, t in g["who"]) + '</div></section>')
                faq_html = '<h2>Questions people ask</h2><div class="faq">' + "".join(f'<details><summary>{E(q)}</summary><p>{E(a)}</p></details>' for q, a in g["faq"]) + '</div>'
                faq_ld = '<script type="application/ld+json">' + json.dumps({"@context": "https://schema.org", "@type": "FAQPage",
                         "mainEntity": [{"@type": "Question", "name": q, "acceptedAnswer": {"@type": "Answer", "text": a}} for q, a in g["faq"]]}) + '</script>'
            else:
                faq_html = ""
            body = (f'<p class="crumbs"><a href="../index.html">Jobs</a> / <a href="../states/{slug(name)}.html">{E(name)}</a> / {E(ci)}</p>'
                    f'<h1>Data center jobs in {E(ci)}, {s}</h1>'
                    f'<p class="lede">{n:,} open technician jobs in {E(ci)} from {len({j["company"] for j in rows})} employers, read daily from their career pages. '
                    + (f'Typical posted pay: <b>{money(statistics.median([j["hourly_min"] for j in rows if j["hourly_min"]]))}–{money(statistics.median([j["hourly_max"] for j in rows if j["hourly_min"]]))}/hr</b>.' if any(j["hourly_min"] for j in rows) else '')
                    + '</p>' + guide_html
                    + '<h2>Pay by employer</h2>' + self.pay_table(rows, lambda j: j["company"], "Employer", 1, lambda k: f"companies/{slug(k)}.html")
                    + '<h2>Open jobs</h2>' + self.job_list(rows, 1) + faq_html
                    + f'<p class="note">See also: <a href="../states/{slug(name)}.html">all {E(name)} data center jobs</a>, <a href="../travel-jobs.html">jobs with per diem and housing</a>, <a href="../entry-level-jobs.html">entry-level jobs</a>.</p>'
                    + self.signup())
            self.page(f"cities/{slug(ci + '-' + s)}.html", f"{ci} Data Center Jobs: {n:,} Technician Openings with Pay | {SITE_NAME}",
                      f"{n:,} data center technician jobs in {ci}, {s} with posted pay by employer. Updated {self.today:%B %-d, %Y}.", body,
                      head_extra=self.breadcrumbs([("Jobs", "index.html"), (name, f"states/{slug(name)}.html"), (ci, f"cities/{slug(ci + '-' + s)}.html")]) + faq_ld)

        # ---- job pages (full build only), with JobPosting structured data for Google
        if not self.preview:
            for j in js:
                posted_d = date.fromisoformat(j["posted"]) if j["posted"] else self.today
                valid = max(posted_d, self.today - timedelta(days=1)) + timedelta(days=45)
                perks_txt = ", ".join(perk_labels(j))
                ld = {"@context": "https://schema.org/", "@type": "JobPosting", "title": clean_title(j["title"]),
                      "description": f"<p>{E(clean_title(j['title']))} at {E(j['company'])} in {E(j['city'])}, {j['state']}. "
                                     + (f"Posted pay: {E(money(j['pay_min'], j['pay_unit']))}–{E(money(j['pay_max'], j['pay_unit']))} per {j['pay_unit']}. " if j["pay_min"] else "")
                                     + (f"Employer mentions: {E(perks_txt)}. " if perks_txt else "")
                                     + f"Job type: {E(ROLE_EN.get(j['role'], j['role']))}. Apply on the employer's career site.</p>",
                      "datePosted": str(posted_d), "validThrough": f"{valid}T23:59:59",
                      "employmentType": "FULL_TIME",
                      "identifier": {"@type": "PropertyValue", "name": j["company"], "value": str(j["job_id"])},
                      "hiringOrganization": {"@type": "Organization", "name": j["company"]},
                      "jobLocation": {"@type": "Place", "address": {"@type": "PostalAddress", "addressLocality": j["city"],
                                                                     "addressRegion": j["state"], "addressCountry": "US"}},
                      "directApply": False}
                crumbs_ld = self.breadcrumbs([("Jobs", "index.html"), (j["company"], f"companies/{slug(j['company'])}.html"),
                                              (clean_title(j["title"]), f"jobs/{j['slug']}.html")])
                if j["pay_min"]:
                    ld["baseSalary"] = {"@type": "MonetaryAmount", "currency": "USD",
                                        "value": {"@type": "QuantitativeValue", "minValue": j["pay_min"], "maxValue": j["pay_max"],
                                                  "unitText": "HOUR" if j["pay_unit"] == "hour" else "YEAR"}}
                pay = (f'{money(j["pay_min"], j["pay_unit"])}–{money(j["pay_max"], j["pay_unit"])} per {j["pay_unit"]}'
                       if j["pay_min"] else "Not posted by the employer")
                body = (f'<p class="crumbs"><a href="../index.html">Jobs</a> / <a href="../companies/{slug(j["company"])}.html">{E(j["company"])}</a></p>'
                        f'<h1>{E(clean_title(j["title"]))}</h1>'
                        f'<p class="lede">{E(j["company"])} · {E(j["city"])}, {j["state"]}</p>'
                        '<div class="tablebox"><table><tbody>'
                        f'<tr><th>Posted pay</th><td>{pay}</td></tr>'
                        f'<tr><th>Job type</th><td>{E(ROLE_EN.get(j["role"], j["role"]))}</td></tr>'
                        f'<tr><th>Openings</th><td>{j["openings"]}</td></tr>'
                        + (f'<tr><th>Travel perks</th><td>{", ".join(E(t) for t in perk_labels(j))}</td></tr>' if perk_labels(j) else "")
                        + f'<tr><th>First posted</th><td>{E(j["posted"] or "—")}</td></tr></tbody></table></div>'
                        f'<p><a class="more primary" href="{E(j["url"])}" rel="nofollow noopener" target="_blank">Apply on {E(j["company"])}\'s site</a></p>'
                        f'<h2>More {E(j["company"])} jobs in {E(STATE_NAMES.get(j["state"], j["state"]))}</h2>'
                        + self.job_list([x for x in js if x["company"] == j["company"] and x["state"] == j["state"] and x is not j], 1, 10)
                        + self.signup())
                self.page(f'jobs/{j["slug"]}.html', f'{clean_title(j["title"])} – {j["company"]}, {j["city"]} | {SITE_NAME}',
                          f'{clean_title(j["title"])} at {j["company"]} in {j["city"]}, {j["state"]}. Pay: {pay}.', body,
                          head_extra=f'<script type="application/ld+json">{json.dumps(ld)}</script>{crumbs_ld}')

        # ---- categorías: por tipo de trabajo y por nivel
        role_counts = Counter()
        for j in js:
            role_counts[ROLE_EN.get(j["role"], j["role"])] += j["openings"]
        ROLE_BLURB = {
            "Data center technician": "Rack and stack, cabling, hardware swaps, tickets and documentation inside live data halls. The core technician job at hyperscalers, operators and contractors.",
            "Critical facilities": "Keeping power and cooling alive: UPS, generators, switchgear, chillers, rounds and emergency response. Usually shift work on a rotation.",
            "Install & network": "Structured cabling, fiber splicing and testing, network hardware installs and deployment on new builds and expansions. Where contractors hire most.",
            "Electrical": "Journeyman and apprentice electricians, medium-voltage and low-voltage work on data center construction and maintenance.",
            "Mechanical & HVAC": "Chillers, CRAH/CRAC units, pumps, controls and the mechanical side of cooling.",
            "Controls & BMS": "Building management systems, PLCs, controls commissioning and tuning.",
            "Power & generators": "Generator, turbine and power-plant technicians supporting campus power.",
            "Operations center": "Control-room and NOC/SOC operators monitoring alarms, access and systems.",
            "Construction site": "Field engineers and site technicians on active data center construction projects.",
            "IT support": "Hands-on IT support roles based inside data centers.",
            "Other technician": "Technician roles that don't fit the other categories.",
        }
        LEVEL_BLURB = {
            "I": ("Level I / entry", "First-rung technician roles: no data center experience required, training on the job. Often 12-hour shifts on construction sites or nights in live facilities."),
            "II": ("Level II", "1–3 years of experience: works independently on installs, troubleshooting and documentation; often trains Level I techs."),
            "III": ("Level III / senior", "Senior techs, leads and foremen: own a scope or a crew, handle escalations, quality and commissioning support."),
            "IV": ("Level IV", "Principal and chief-engineer level technician roles."),
        }
        for role_en, n in role_counts.most_common():
            rows = [j for j in js if ROLE_EN.get(j["role"], j["role"]) == role_en]
            lv = Counter(j["level"] or "—" for j in rows)
            body = (f'<p class="crumbs"><a href="../index.html">Jobs</a> / <a href="../index.html#browse">Categories</a> / {E(role_en)}</p>'
                    f'<h1>{E(role_en)} jobs in data centers</h1>'
                    f'<p class="lede">{n:,} open {E(role_en.lower())} jobs. {E(ROLE_BLURB.get(role_en, ""))}</p>'
                    '<h2>Pay by employer</h2>' + self.pay_table(rows, lambda j: j["company"], "Employer", 1, lambda k: f"companies/{slug(k)}.html")
                    + '<h2>By level</h2><div class="quick">' + "".join(f'<a href="../levels/{slug(l)}.html">Level {E(l)} <small>{c}</small></a>' for l, c in sorted(lv.items()) if l != "—") + '</div>'
                    + '<h2>Open jobs</h2>' + self.job_list(rows, 1) + self.signup())
            self.page(f"roles/{slug(role_en)}.html", f"{role_en} Jobs in Data Centers: {n:,} Open with Pay | {SITE_NAME}",
                      f"{n:,} {role_en.lower()} jobs in US data centers with posted pay by employer and level. Updated {self.today:%B %-d, %Y}.", body,
                      head_extra=self.breadcrumbs([("Jobs", "index.html"), (role_en, f"roles/{slug(role_en)}.html")]))
        for lvl, (lname, blurb) in LEVEL_BLURB.items():
            rows = [j for j in js if j.get("level") == lvl]
            if not rows:
                continue
            n = sum(j["openings"] for j in rows)
            paid = [j for j in rows if j["hourly_min"]]
            lo = statistics.median([j["hourly_min"] for j in paid]) if paid else None
            hi = statistics.median([j["hourly_max"] for j in paid]) if paid else None
            body = (f'<p class="crumbs"><a href="../index.html">Jobs</a> / <a href="../index.html#browse">Categories</a> / {E(lname)}</p>'
                    f'<h1>{E(lname)} data center technician jobs</h1>'
                    f'<p class="lede">{n:,} open jobs. {E(blurb)}' + (f' Typical posted pay: <b>{money(lo)}–{money(hi)}/hr</b>.' if lo else '') + '</p>'
                    '<h2>Pay by employer</h2>' + self.pay_table(rows, lambda j: j["company"], "Employer", 1, lambda k: f"companies/{slug(k)}.html")
                    + '<h2>Open jobs</h2>' + self.job_list(rows, 1) + self.signup())
            self.page(f"levels/{slug(lvl)}.html", f"{lname} Data Center Technician Jobs and Pay | {SITE_NAME}",
                      f"{n:,} {lname.lower()} data center technician jobs with posted pay by employer. Updated {self.today:%B %-d, %Y}.", body,
                      head_extra=self.breadcrumbs([("Jobs", "index.html"), (lname, f"levels/{slug(lvl)}.html")]))

        # ---- entry-level jobs: no experience / level I
        entry = [j for j in js if j.get("entry")]
        e_paid = [j for j in entry if j["hourly_min"]]
        e_lo = statistics.median([j["hourly_min"] for j in e_paid]) if e_paid else None
        e_hi = statistics.median([j["hourly_max"] for j in e_paid]) if e_paid else None
        e_states = Counter()
        e_cos = Counter()
        for j in entry:
            e_states[j["state"]] += j["openings"]
            e_cos[j["company"]] += j["openings"]
        e_state_links = "".join(f'<li><a href="states/{slug(STATE_NAMES.get(st, st))}.html"><span>{E(STATE_NAMES.get(st, st))}</span><small>{n}</small></a></li>'
                                for st, n in e_states.most_common(12))
        e_co_links = "".join(f'<li><a href="companies/{slug(c)}.html">{logo(c)}<span>{E(c)}</span><small>{n}</small></a></li>'
                             for c, n in e_cos.most_common(12))
        faq = [
            ("Can I get a data center job with no experience?",
             "Yes. Level I technician, cable puller, deployment technician and fiber technician 1 roles are hired without data center experience. "
             "Employers usually ask for a high school diploma or GED, a clean drug test and background check, the ability to lift 50 lb and work 10–12 hour shifts, and a driver's license. "
             "Contractors that build and cable data centers hire entry-level techs fastest; hyperscalers like Amazon hire Data Center Technician I roles directly."),
            ("How much do entry-level data center technicians make?",
             (f"Employers on this site currently post a typical range of {money(e_lo)}–{money(e_hi)} per hour for entry-level technician roles, " if e_lo else "Entry-level technician roles on this site typically post $20–$30 per hour, ")
             + "with overtime common on construction sites. Traveling contractor jobs often add per diem ($100–$200 a day) and housing on top of the hourly rate."),
            ("What certifications help you get hired?",
             "None are required for most Level I jobs, but OSHA 10 (construction) and a forklift or scissor-lift card get you on site faster. "
             "For a long-term edge: CompTIA A+ or Network+ for operations roles, BICSI Installer 1 or FOA CFOT for structured cabling and fiber."),
            ("What does an entry-level data center technician actually do?",
             "Racking and stacking servers, running and labeling copper and fiber cable, terminating and testing, moving equipment, following checklists and documenting work. "
             "On construction projects it is physical work in 12-hour shifts; in live data centers it is more operations: tickets, swaps, inventory."),
            ("Is it a good career path?",
             "Level I techs commonly move to Level II–III in 1–3 years ($30–$45/hr), then lead, foreman or critical facilities roles. "
             "Data center construction is one of the fastest-growing trades in the US, with new campuses in Texas, Ohio, Arizona, Virginia, Wisconsin and Louisiana."),
        ]
        faq_html = "".join(f'<details><summary>{E(q)}</summary><p>{E(a)}</p></details>' for q, a in faq)
        faq_ld = {"@context": "https://schema.org", "@type": "FAQPage",
                  "mainEntity": [{"@type": "Question", "name": q, "acceptedAnswer": {"@type": "Answer", "text": a}} for q, a in faq]}
        body = ('<p class="crumbs"><a href="index.html">Jobs</a> / Entry level</p>'
                '<h1>Entry-level data center jobs: no experience required</h1>'
                f'<p class="lede">{sum(j["openings"] for j in entry):,} open entry-level data center jobs — Level I technicians, cable pullers, deployment and fiber techs — at {len(e_cos)} employers. '
                + (f'Typical posted pay: <b>{money(e_lo)}–{money(e_hi)}/hr</b>. ' if e_lo else '')
                + 'Tagged automatically when the employer\'s posting says Level I, entry level, no experience required or paid training.</p>'
                '<section class="guide"><h2>How to get your first data center job</h2><div class="prose">'
                '<p><b>What they ask for.</b> High school diploma or GED, pass a drug test and background check, lift 50 lb, stand and climb ladders all shift, '
                'a valid driver\'s license, and willingness to work nights, weekends or 10–12 hour shifts. Many contractor jobs also want OSHA 10.</p>'
                '<p><b>Where the doors are open.</b> Contractors that build and cable data centers (deployment, structured cabling, fiber) hire the most entry-level techs and train on the job. '
                'Hyperscalers (Amazon, Google, Microsoft) and operators (QTS, Equinix) post Level I technician roles with better benefits but more competition. Staffing firms place techs on 6–12 month projects quickly.</p>'
                '<p><b>What makes you stand out.</b> Any hands-on experience: electrical helper, cable installer, IT help desk, military, warehouse with forklift. '
                'A $40 OSHA 10 card and a CompTIA A+ or BICSI Installer 1 cert put you ahead of most applicants. Say in your application that you can travel and work 12s if you can — it matters more than a degree.</p>'
                '<p>Step by step, with a 90-day plan: <a href="how-to-become-a-data-center-technician.html">how to become a data center technician</a>.</p>'
                '<p><b>What to ask before you accept.</b> Hourly rate, overtime after 40 or after 8, per diem and whether housing is paid, the rotation (weeks on/off), '
                'and whether the position is W-2 or 1099. See <a href="travel-jobs.html">jobs with per diem and housing</a> and the <a href="shift-schedules.html">shift schedule guide</a>.</p>'
                '</div></section>'
                '<h2>Where entry-level jobs are</h2>' + f'<ul class="grid-links">{e_state_links}</ul>'
                '<h2>Employers hiring entry-level techs</h2>' + f'<ul class="grid-links">{e_co_links}</ul>'
                '<h2>Open entry-level jobs</h2>' + self.job_list(entry, 0)
                + '<h2>Questions people ask</h2><div class="faq">' + faq_html + '</div>'
                + self.signup())
        self.page("entry-level-jobs.html", f"Entry-Level Data Center Jobs (No Experience) {self.today.year}: Pay &amp; How to Start | {SITE_NAME}".replace("&amp;", "&"),
                  f"{sum(j['openings'] for j in entry):,} entry-level data center technician jobs with no experience required, posted pay ranges, "
                  "requirements, certifications that help and how to get hired.", body,
                  head_extra=f'<script type="application/ld+json">{json.dumps(faq_ld)}</script>')

        # ---- new this week: recién publicados + RSS
        fresh = sorted([j for j in js if j.get("days_posted") is not None and j["days_posted"] <= 7],
                       key=lambda j: (j["days_posted"], -(j["hourly_max"] or 0)))
        by_day = defaultdict(list)
        for j in fresh:
            by_day[j["days_posted"]].append(j)
        day_label = lambda d: "Today" if d == 0 else ("Yesterday" if d == 1 else f"{d} days ago")  # noqa: E731
        sections = "".join(f'<h2>{day_label(d)} <small>({sum(j["openings"] for j in by_day[d])} openings)</small></h2>' + self.job_list(by_day[d], 0)
                           for d in sorted(by_day))
        new_cos = sorted({j["company"] for j in fresh})
        body = ('<p class="crumbs"><a href="index.html">Jobs</a> / New this week</p>'
                '<h1>New data center jobs this week</h1>'
                f'<p class="lede">{sum(j["openings"] for j in fresh):,} technician openings posted in the last 7 days by {len(new_cos)} employers, newest first. '
                f'Listings that employers take down disappear from this site the next morning, so everything here is live as of {self.today:%B %-d}.</p>'
                f'<p class="note">Get these by email every Monday, or subscribe to the <a href="feed.xml">RSS feed</a>.</p>'
                + sections + self.signup())
        self.page("new-jobs.html", f"New Data Center Technician Jobs Posted This Week | {SITE_NAME}",
                  f"Data center technician, fiber and electrician jobs posted in the last 7 days, with pay. Updated {self.today:%B %-d, %Y}.", body)
        if not self.preview:
            items = "".join(
                f"<item><title>{E(clean_title(j['title']))} – {E(j['company'])}, {E(j['city'])}, {j['state']}</title>"
                f"<link>{E(SITE_URL + '/jobs/' + j['slug'] + '.html')}</link><guid>{E(SITE_URL + '/jobs/' + j['slug'] + '.html')}</guid>"
                f"<pubDate>{E(j['posted'] or str(self.today))}</pubDate>"
                f"<description>{E((money(j['hourly_min']) + '–' + money(j['hourly_max']) + '/hr. ') if j['hourly_min'] else 'Pay not posted. ')}{E(', '.join(perk_labels(j)))}</description></item>"
                for j in fresh[:100])
            (self.out / "feed.xml").write_text('<?xml version="1.0" encoding="UTF-8"?><rss version="2.0"><channel>'
                                               f'<title>{E(SITE_NAME)}: new technician jobs</title><link>{E(SITE_URL)}/new-jobs.html</link>'
                                               f'<description>Data center technician jobs posted this week, with pay.</description>{items}</channel></rss>', encoding="utf-8")

        # ---- travel jobs: per diem, housing, rotations
        travel = [j for j in js if j.get("perks")]
        pd = [j for j in travel if j.get("per_diem")]
        by_co = Counter()
        for j in travel:
            by_co[j["company"]] += j["openings"]
        co_rows = "".join(f'<tr><td><a href="companies/{slug(c)}.html">{E(c)}</a></td><td class=num>{n}</td>'
                          f'<td>{E(", ".join(sorted({t for j in travel if j["company"] == c for t in perk_labels(j)})))}</td></tr>'
                          for c, n in by_co.most_common())
        med_pd = statistics.median([j["per_diem"] for j in pd]) if pd else None
        body = ('<p class="crumbs"><a href="index.html">Jobs</a> / Per diem &amp; housing</p>'
                '<h1>Travel jobs with per diem, housing and rotations</h1>'
                f'<p class="lede">{sum(j["openings"] for j in travel):,} openings where the employer\'s own posting mentions per diem, paid housing or lodging, '
                f'a travel rotation, overtime or a bonus. {len(pd)} postings state the per diem amount'
                + (f' (typical: {money(med_pd).replace(".00", "")}/day).' if med_pd else '.')
                + ' For a traveling tech, $28/hr plus $150/day and a hotel beats $34/hr with nothing — this page is where you compare that.</p>'
                '<p class="note">We only tag what the employer wrote in the posting. If a perk is not listed here, ask the recruiter; many contractors pay per diem without posting it.</p>'
                '<h2>Employers posting travel perks</h2><div class="tablebox"><table><thead><tr><th>Employer</th><th>Openings</th><th>Perks mentioned</th></tr></thead>'
                f'<tbody>{co_rows}</tbody></table></div>'
                '<h2>Open jobs</h2>' + self.job_list(travel, 0) + self.signup())
        self.page("travel-jobs.html", f"Data Center Travel Jobs with Per Diem and Housing | {SITE_NAME}",
                  "Data center technician and fiber jobs that pay per diem, provide housing or run on a travel rotation, with pay ranges.", body)

        # ---- about + survey
        self.page("about.html", f"About: Who Runs {SITE_NAME} and Where the Data Comes From", f"Why {SITE_NAME} exists, who built it, how listings are collected and how pay is calculated.",
                  '<p class="crumbs"><a href="index.html">Jobs</a> / About</p><h1>Made by a tech, for techs</h1>'
                  f'<div class="prose"><p>{E(OWNER_BLURB)}</p>'
                  '<h2 id="who">Who runs this</h2>'
                  '<p>Enmanuel V., an inside-plant (ISP) technician who has worked structured cabling and fiber on hyperscale data center builds in Texas, '
                  'including the Abilene campus, on 12-hour shifts six days a week. This site started as the list he wished he had: every technician job, the pay, '
                  'and whether the contractor pays per diem — without a recruiter in the middle.</p>'
                  '<h2 id="data">Where the data comes from</h2>'
                  f'<p>Every morning a script reads the career pages of {len(companies)} data center operators and contractors (Amazon, Google, Microsoft, QTS, Equinix, '
                  'NTI, AFL, Team LINX, E2 Optics, ADB, Black Box and more) and keeps only technician, electrician, fiber and cabling roles. '
                  'No staffing-agency reposts, no call-center jobs, no fake "data entry" listings. When an employer takes a listing down, it disappears here the next morning.</p>'
                  '<h2 id="pay">How pay is calculated</h2>'
                  '<p>We show the pay range only when the employer posts one — never estimates. Salaried ranges are divided by 2,080 hours so a salaried '
                  'Google role and an hourly Amazon role line up. Per diem, housing, rotations and schedules are tagged only when the posting states them.</p>'
                  '<h2 id="corrections">Corrections</h2>'
                  '<p>If a listing, pay figure or company description is wrong, say so through the <a href="shift-survey.html">survey form</a> and it gets fixed in the next build. '
                  'We never publish site names, badge or access details, or anything a technician tells us in confidence.</p>'
                  '<p>Next up: real shift schedules and site conditions reported by technicians. If you work in a data center, '
                  '<a href="shift-survey.html">add yours in two minutes</a>.</p></div>' + self.signup(), head_extra=self.org_ld())
        self.page("shift-survey.html", f"Data Center Shift Survey | {SITE_NAME}",
                  "Tell other technicians what your shift, rotation and pay really look like. Anonymous.",
                  '<p class="crumbs"><a href="index.html">Jobs</a> / Shift survey</p><h1>What does your shift really look like?</h1>'
                  '<div class="prose"><p>Job posts say "must work nights, weekends and holidays." They never say which rotation, how overtime works, '
                  'or whether you can switch to days. Techs know. Share yours anonymously and see what others report.</p>'
                  '<p class="note">We only ask about schedule, pay and general conditions. Never share site names, room locations, access '
                  'procedures or anything your employer considers confidential.</p></div>'
                  + (f'<p><a class="more primary" href="{E(SURVEY_URL)}" rel="noopener" target="_blank">Take the 2-minute survey</a></p>' if SURVEY_URL
                   else '<p class="callout">The survey opens soon. Join the weekly list below and we will send you the link.</p>') + self.signup())

        # ---- content pages (content/*.html): first lines carry <!--title: ...--> and <!--desc: ...-->
        for f in sorted(Path(__file__).with_name("content").glob("*.html")):
            raw = f.read_text(encoding="utf-8")
            t = re.search(r"<!--title: (.*?)-->", raw).group(1)
            dsc = re.search(r"<!--desc: (.*?)-->", raw).group(1)
            self.page(f.name, t, dsc, re.sub(r"<!--.*?-->", "", raw) + self.signup())

        # ---- recursos estáticos (ícono, imagen para compartir)
        import shutil
        for name in ("favicon.svg", "apple-touch-icon.png", "og.png"):
            src = Path(__file__).with_name(name)
            if src.exists():
                shutil.copy(src, self.out / name)

        # ---- sitemap/robots (full build)
        if not self.preview:
            posted_by_slug = {j["slug"]: (j["posted"] or str(self.today)) for j in js}
            def urlset(paths, lastmod):
                body = "".join(f"<url><loc>{E(SITE_URL + '/' + p.replace('index.html', ''))}</loc><lastmod>{lastmod(p)}</lastmod></url>" for p in paths)
                return f'<?xml version="1.0" encoding="UTF-8"?><urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">{body}</urlset>'
            job_pages = [p for p in self.pages if p.startswith("jobs/")]
            hub_pages = [p for p in self.pages if not p.startswith("jobs/")]
            (self.out / "sitemap-pages.xml").write_text(urlset(hub_pages, lambda p: str(self.today)), encoding="utf-8")
            (self.out / "sitemap-jobs.xml").write_text(urlset(job_pages, lambda p: posted_by_slug.get(p[5:-5], str(self.today))), encoding="utf-8")
            (self.out / "sitemap.xml").write_text('<?xml version="1.0" encoding="UTF-8"?><sitemapindex xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">'
                                                  f'<sitemap><loc>{SITE_URL}/sitemap-pages.xml</loc><lastmod>{self.today}</lastmod></sitemap>'
                                                  f'<sitemap><loc>{SITE_URL}/sitemap-jobs.xml</loc><lastmod>{self.today}</lastmod></sitemap></sitemapindex>', encoding="utf-8")
            (self.out / "robots.txt").write_text(f"User-agent: *\nAllow: /\nSitemap: {SITE_URL}/sitemap.xml\n")
            self.page("404.html", f"Job closed or page not found | {SITE_NAME}", "This job was taken down by the employer or the page moved.",
                      '<h1>That job is closed or the page moved</h1>'
                      '<p class="lede">Employers take listings down when they fill them, and this site removes them the next morning. The ones below are live today.</p>'
                      '<div class="quick"><a href="/index.html">All technician jobs</a><a href="/new-jobs.html">New this week</a><a href="/entry-level-jobs.html">Entry level</a>'
                      '<a href="/travel-jobs.html">Per diem &amp; housing</a><a href="/states.html">By state</a><a href="/companies.html">By company</a></div>'
                      + '<h2>Newest openings</h2>' + self.job_list(sorted(js, key=lambda j: j["days_posted"] if j["days_posted"] is not None else 999)[:10], 0),
                      canonical=False)
            self.pages.remove("404.html")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", default="data/jobs.json")
    ap.add_argument("--out", default="site")
    ap.add_argument("--preview", action="store_true")
    ap.add_argument("--today")
    a = ap.parse_args()
    jobs = json.loads(Path(a.data).read_text())
    seen = Counter()
    for j in jobs:
        s = slug(f'{j["company"]}-{clean_title(j["title"])}-{j["city"]}-{j["state"]}')[:90]
        seen[s] += 1
        j["slug"] = s if seen[s] == 1 else f"{s}-{seen[s]}"
    today = date.fromisoformat(a.today) if a.today else date.today()
    site = Site(jobs, Path(a.out), a.preview, today)
    sp = Path(a.data).with_name("survey.json")
    site.survey = json.loads(sp.read_text()) if sp.exists() else {"companies": {}}
    site.build()
    print(f"{len(site.pages)} páginas -> {a.out}")


if __name__ == "__main__":
    main()
