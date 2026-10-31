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
from datetime import date
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


LOGO_COLORS = ["#2b6cb0", "#1f7a4d", "#6b46c1", "#b7791f", "#c53030", "#2c7a7b", "#4a5568", "#d53f8c", "#3182ce", "#805ad5"]


def logo(company: str) -> str:
    """Avatar de letras para la empresa (sin usar logotipos ajenos)."""
    words = [w for w in re.split(r"[\s(]+", company) if w and w[0].isalpha()]
    txt = (words[0][:2] if len(words) == 1 else "".join(w[0] for w in words[:2])).upper()
    col = LOGO_COLORS[sum(map(ord, company)) % len(LOGO_COLORS)]
    return f'<span class="logo" style="background:{col}" aria-hidden="true">{E(txt)}</span>'


def clean_title(t: str) -> str:
    t = re.sub(r"\s+,", ",", t)
    t = re.sub(r",\s*(DCC Communities|Amazon Web Services|AWS Support|AWS)\b", "", t)
    return re.sub(r"\s{2,}", " ", t).strip(" ,-")


# ---------------------------------------------------------------------------
# Estilos y plantilla
# ---------------------------------------------------------------------------
CSS = (Path(__file__).with_name("theme.css")).read_text(encoding="utf-8")

FONTS = ('<link rel="preconnect" href="https://fonts.googleapis.com"><link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>'
         '<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Barlow+Condensed:wght@600;700'
         '&family=JetBrains+Mono:wght@400;500;600&family=Source+Sans+3:wght@400;600;700&display=swap">')


PERK_EN = {"per_diem": "Per diem", "housing": "Housing", "travel": "Travel", "overtime": "Overtime", "signon": "Sign-on bonus",
           "relocation": "Relocation", "shift_diff": "Shift differential", "vehicle": "Company vehicle", "retention": "Completion bonus"}


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


class Site:
    def __init__(self, jobs, out: Path, preview: bool, today: date):
        self.jobs, self.out, self.preview, self.today = jobs, out, preview, today
        self.pages: list[str] = []

    def rel(self, path: str, depth: int) -> str:
        return "../" * depth + path

    def page(self, path: str, title: str, desc: str, body: str, canonical: bool = True, head_extra: str = ""):
        depth = path.count("/")
        r = lambda p: self.rel(p, depth)  # noqa: E731
        nav = (f'<nav class="main" aria-label="Main"><a href="{r("index.html")}">Jobs</a>'
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
             + FONTS + f"<style>{CSS}</style>{head_extra}"
             + ("" if bare else "</head><body>")
             + f'<header class="site"><div class="wrap"><a class="brand" href="{r("index.html")}"><i aria-hidden="true"></i>Data Center <em>Job USA</em></a>{nav}</div></header>'
             + (f'<main>{body}</main>' if body.startswith('<section class="hero">') else f'<main><div class="wrap">{body}</div></main>')
             + f'<footer class="site"><div class="wrap"><span>{E(SITE_NAME)} · {E(SITE_TAGLINE)}</span>'
             + f'<span>Pay ranges come from each employer\'s own posting · Updated {self.today:%B %-d, %Y} · <a href="{r("about.html")}">About</a> · <a href="{r("shift-survey.html")}">Shift survey</a></span></div></footer>'
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
        if j["openings"] > 1:
            chips += f' <span class="chip">{j["openings"]} openings</span>'
        if j.get("days_posted") is not None and j["days_posted"] <= 7:
            chips += ' <span class="chip new">New</span>'
        chips += self.perk_chips(j)
        if j["hourly_min"]:
            lo, hi = j["hourly_min"], j["hourly_max"] or j["hourly_min"]
            left, width = lo / scale_max * 100, max(2, (hi - lo) / scale_max * 100)
            pay = (f'<div class="pay">{money(lo)}–{money(hi)}<small>per hour'
                   + (f' · {money(j["pay_min"], "year")}–{money(j["pay_max"], "year")}/yr' if j["pay_unit"] == "year" else "")
                   + f'</small><div class="bar" aria-hidden="true"><span style="left:{left:.1f}%;width:{width:.1f}%"></span></div></div>')
        else:
            pay = '<div class="pay nopay">Pay not posted</div>'
        return (f'<li class="job">{logo(j["company"])}<div><a class="t" href="{E(href)}"{ext}>{E(title)}</a>'
                f'<div class="meta"><span class="co">{E(j["company"])}</span><span>{E(loc)}</span>{chips}</div></div>{pay}</li>')

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
                 "hi": j["hourly_max"], "d": j["days_posted"], "p": perk_labels(j),
                 "u": (f'jobs/{j["slug"]}.html' if not self.preview else j["url"])} for j in js]
        opts = lambda vals: "".join(f'<option value="{E(v)}">{E(v)}</option>' for v in vals)  # noqa: E731
        scale = max([j["hourly_max"] or 0 for j in js] + [1])
        top_states = [(STATE_NAMES.get(st, st), f"states/{slug(STATE_NAMES.get(st, st))}.html") for st, _ in states.most_common(4)]
        quick = ("".join(f'<a href="{E(u)}">{E(n)}</a>' for n, u in top_states)
                 + '<a href="travel-jobs.html">Per diem &amp; housing</a><a href="salaries.html">Compare pay</a><a href="shift-schedules.html">Shift schedules</a><a href="shift-survey.html">Tech survey</a>')
        body = ('<section class="hero"><div class="wrap">'
                '<p class="kicker">Built by a working data center tech</p>'
                '<h1>Data center tech jobs with the <mark>pay up front</mark>.</h1>'
                f'<p class="lede">{total:,} open technician jobs at {len(companies)} data center operators and contractors, pulled straight from their own career pages every morning. '
                f'{paid / total:.0%} show the pay range, and you can sort by it. No agencies, no call centers.</p>'
                f'<div class="quick">{quick}</div></div></section><div class="wrap">'
                f'<div class="stats"><div class="stat"><b>{total:,}</b><span>open technician jobs</span></div>'
                f'<div class="stat"><b>{len(companies)}</b><span>employers tracked</span></div>'
                f'<div class="stat"><b>{len(states)}</b><span>states</span></div>'
                f'<div class="stat"><b>{paid / total:.0%}</b><span>with pay posted</span></div></div>'
                '<form class="filters" id="f" onsubmit="event.preventDefault()">'
                '<label for="q">Search<input id="q" type="search" placeholder="Title or city"></label>'
                f'<label for="st">State<select id="st"><option value="">All states</option>{opts(sorted(states))}</select></label>'
                f'<label for="co">Company<select id="co"><option value="">All companies</option>{opts(sorted(companies))}</select></label>'
                f'<label for="ro">Type<select id="ro"><option value="">All types</option>{opts(sorted({d["r"] for d in data}))}</select></label>'
                '<label for="pay">Min $/hr<input id="pay" type="number" min="0" step="1" placeholder="e.g. 35"></label>'
                '<label for="pk">Perks<select id="pk"><option value="">Any</option><option value="Per diem">Per diem</option><option value="Housing">Housing / lodging</option>'
                '<option value="Travel">Travel job</option><option value="Schedule">Schedule stated (12s, 6 days…)</option><option value="Overtime">Overtime</option><option value="Sign-on bonus">Sign-on bonus</option></select></label>'
                '<label for="so">Sort<select id="so"><option value="pay">Highest pay</option><option value="new">Newest</option></select></label>'
                '</form><p class="count" id="cnt" aria-live="polite"></p><ul class="jobs" id="list"></ul>'
                '<button class="more" id="more" type="button">Show more jobs</button>'
                + self.signup()
                + f'<script>const J={json.dumps(data, separators=(",", ":"))};const SC={scale};const LG={json.dumps({c: logo(c) for c in companies})};const ST={json.dumps({s: STATE_NAMES.get(s, s) for s in states})};'
                + r"""
const $=id=>document.getElementById(id);let N=40;
const esc=s=>String(s).replace(/[&<>"]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]));
const m=v=>'$'+v.toFixed(2);
function row(j){let pay='<div class="pay nopay">Pay not posted</div>';
 if(j.lo){const l=j.lo/SC*100,w=Math.max(2,(j.hi-j.lo)/SC*100);pay=`<div class="pay">${m(j.lo)}–${m(j.hi)}<small>per hour</small><div class="bar" aria-hidden="true"><span style="left:${l.toFixed(1)}%;width:${w.toFixed(1)}%"></span></div></div>`}
 const ext=/^https?:/.test(j.u)?' rel="noopener" target="_blank"':'';
 return `<li class="job">${LG[j.c]||''}<div><a class="t" href="${esc(j.u)}"${ext}>${esc(j.t)}</a><div class="meta"><span class="co">${esc(j.c)}</span><span>${j.ci?esc(j.ci)+', '+j.s:esc(ST[j.s]||j.s)}</span><span class="chip">${esc(j.r)}</span>${j.n>1?`<span class="chip">${j.n} openings</span>`:''}${j.d!==null&&j.d<=7?'<span class="chip new">New</span>':''}${(j.p||[]).map(t=>`<span class="chip perk">${esc(t)}</span>`).join('')}</div></div>${pay}</li>`}
function draw(){const q=$('q').value.trim().toLowerCase(),st=$('st').value,co=$('co').value,ro=$('ro').value,p=parseFloat($('pay').value)||0,so=$('so').value,pk=$('pk').value;
 let r=J.filter(j=>(!q||(j.t+' '+j.ci).toLowerCase().includes(q))&&(!st||j.s===st)&&(!co||j.c===co)&&(!ro||j.r===ro)&&(!p||(j.hi||0)>=p)&&(!pk||(j.p||[]).some(t=>t.startsWith(pk))));
 r.sort(so==='new'?(a,b)=>(a.d??999)-(b.d??999):(a,b)=>(b.hi||0)-(a.hi||0));
 const n=r.reduce((s,j)=>s+j.n,0);$('cnt').textContent=`${n.toLocaleString()} openings in ${r.length.toLocaleString()} listings`;
 $('list').innerHTML=r.slice(0,N).map(row).join('');$('more').hidden=r.length<=N}
['q','st','co','ro','pay','pk','so'].forEach(id=>$(id).addEventListener('input',()=>{N=40;draw()}));
$('more').addEventListener('click',()=>{N+=40;draw()});draw();
</script></div>""")
        self.page("index.html", SITE_NAME if self.preview else f"{SITE_NAME}: {SITE_TAGLINE}",
                  f"{total:,} data center technician jobs with pay ranges, from {len(companies)} employers.", body)

        # ---- salaries
        body = ('<p class="crumbs"><a href="index.html">Jobs</a> / Salaries</p>'
                '<h1>Data center technician pay, compared</h1>'
                '<p class="lede">What employers actually post for technician jobs, converted to an hourly rate so salaried and hourly jobs line up. '
                '"Typical" is the median of the posted ranges.</p>'
                '<h2>By employer</h2>' + self.pay_table(js, lambda j: j["company"], "Employer", 0, lambda k: f"companies/{slug(k)}.html")
                + '<h2>By job type</h2>' + self.pay_table(js, lambda j: ROLE_EN.get(j["role"], j["role"]), "Job type", 0)
                + '<h2>By state</h2>' + self.pay_table(js, lambda j: STATE_NAMES.get(j["state"], j["state"]), "State", 0,
                                                      lambda k: f"states/{slug(k)}.html")
                + '<p class="note">Salaried ranges are divided by 2,080 hours. Pay ranges are the employer\'s posted range for the role, not what any one person earns. '
                  'Amazon, Google and Microsoft post pay in every state; some employers only post it where state law requires.</p>'
                + self.signup())
        self.page("salaries.html", f"Data Center Technician Salary by Company and State | {SITE_NAME}",
                  "Posted pay ranges for data center technicians at Amazon, Google, Microsoft and more, by company, job type and state.", body)

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
            body = (f'<p class="crumbs"><a href="../index.html">Jobs</a> / <a href="../companies.html">Companies</a> / {E(c)}</p>'
                    f'<h1>{E(c)} data center technician jobs</h1>'
                    f'<p class="lede">{n:,} open technician jobs at {E(c)} across {len(cs)} states.</p>'
                    '<h2>Pay by job type</h2>' + self.pay_table(rows, lambda j: ROLE_EN.get(j["role"], j["role"]), "Job type", 1)
                    + '<h2>Where they are hiring</h2>' + f'<ul class="grid-links">{st_links}</ul>'
                    + '<h2>Open jobs</h2>' + self.job_list(rows, 1) + self.signup())
            self.page(f"companies/{slug(c)}.html", f"{c} Data Center Technician Jobs and Pay | {SITE_NAME}",
                      f"{n:,} open {c} data center technician jobs with posted pay ranges.", body)

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
            body = (f'<p class="crumbs"><a href="../index.html">Jobs</a> / <a href="../states.html">States</a> / {E(name)}</p>'
                    f'<h1>Data center technician jobs in {E(name)}</h1>'
                    f'<p class="lede">{n:,} open technician jobs in {len(cities)} {"city" if len(cities) == 1 else "cities"}.</p>'
                    '<h2>Pay by employer</h2>' + self.pay_table(rows, lambda j: j["company"], "Employer", 1, lambda k: f"companies/{slug(k)}.html")
                    + '<h2>Cities</h2>' + f'<ul class="grid-links">{c_links}</ul>'
                    + '<h2 id="jobs">Open jobs</h2>' + self.job_list(rows, 1) + self.signup())
            self.page(f"states/{slug(name)}.html", f"Data Center Technician Jobs in {name} | {SITE_NAME}",
                      f"{n:,} data center technician jobs in {name} with posted pay ranges.", body)
        for (ci, s) in city_pages:
            rows = [j for j in js if j["city"] == ci and j["state"] == s]
            n = city_counts[(ci, s)]
            name = STATE_NAMES.get(s, s)
            body = (f'<p class="crumbs"><a href="../index.html">Jobs</a> / <a href="../states/{slug(name)}.html">{E(name)}</a> / {E(ci)}</p>'
                    f'<h1>Data center jobs in {E(ci)}, {s}</h1>'
                    f'<p class="lede">{n:,} open technician jobs in {E(ci)}.</p>'
                    '<h2>Pay by employer</h2>' + self.pay_table(rows, lambda j: j["company"], "Employer", 1, lambda k: f"companies/{slug(k)}.html")
                    + '<h2>Open jobs</h2>' + self.job_list(rows, 1) + self.signup())
            self.page(f"cities/{slug(ci + '-' + s)}.html", f"Data Center Jobs in {ci}, {s} | {SITE_NAME}",
                      f"{n:,} data center technician jobs in {ci}, {s} with pay.", body)

        # ---- job pages (full build only), with JobPosting structured data for Google
        if not self.preview:
            for j in js:
                ld = {"@context": "https://schema.org/", "@type": "JobPosting", "title": clean_title(j["title"]),
                      "description": f"<p>{E(clean_title(j['title']))} at {E(j['company'])} in {E(j['city'])}, {j['state']}. "
                                     f"Apply on the employer's career site.</p>",
                      "datePosted": j["posted"] or str(self.today), "employmentType": "FULL_TIME",
                      "hiringOrganization": {"@type": "Organization", "name": j["company"]},
                      "jobLocation": {"@type": "Place", "address": {"@type": "PostalAddress", "addressLocality": j["city"],
                                                                     "addressRegion": j["state"], "addressCountry": "US"}},
                      "directApply": False}
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
                          head_extra=f'<script type="application/ld+json">{json.dumps(ld)}</script>')

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
        self.page("about.html", f"About | {SITE_NAME}", f"Why {SITE_NAME} exists and where the data comes from.",
                  '<p class="crumbs"><a href="index.html">Jobs</a> / About</p><h1>Made by a tech, for techs</h1>'
                  f'<div class="prose"><p>{E(OWNER_BLURB)}</p>'
                  '<p>Every job here comes straight from the employer\'s own career page: Amazon, Google, Microsoft, CoreWeave, xAI and more. '
                  'No staffing-agency reposts, no call-center jobs, no fake "data entry" listings.</p>'
                  '<p>We show the pay range whenever the employer posts one, and convert it to an hourly rate so you can compare a salaried '
                  'Google role with an hourly Amazon role. When a job stays on the employer\'s site, it is still open, so we keep it and show how long it has been posted.</p>'
                  '<p>Next up: real shift schedules and site conditions reported by technicians. If you work in a data center, '
                  '<a href="shift-survey.html">add yours in two minutes</a>.</p></div>' + self.signup())
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

        # ---- sitemap/robots (full build)
        if not self.preview:
            urls = "".join(f"<url><loc>{E(SITE_URL + '/' + p.replace('index.html', ''))}</loc><lastmod>{self.today}</lastmod></url>"
                           for p in self.pages)
            (self.out / "sitemap.xml").write_text('<?xml version="1.0" encoding="UTF-8"?>'
                                                  f'<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">{urls}</urlset>')
            (self.out / "robots.txt").write_text(f"User-agent: *\nAllow: /\nSitemap: {SITE_URL}/sitemap.xml\n")


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
    site.build()
    print(f"{len(site.pages)} páginas -> {a.out}")


if __name__ == "__main__":
    main()
