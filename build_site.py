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

from site_config import (MIN_CITY_OPENINGS, SURVEY_URL, OWNER_BLURB, ROLE_EN, SITE_NAME, SITE_TAGLINE,
                         SITE_URL, STATE_NAMES)

E = html.escape


def slug(s: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", s.lower()).strip("-")


def money(v, unit="hour"):
    if v is None:
        return "—"
    return f"${v:,.2f}" if unit == "hour" else f"${v:,.0f}"


def clean_title(t: str) -> str:
    t = re.sub(r"\s+,", ",", t)
    t = re.sub(r",\s*(DCC Communities|Amazon Web Services|AWS Support|AWS)\b", "", t)
    return re.sub(r"\s{2,}", " ", t).strip(" ,-")


# ---------------------------------------------------------------------------
# Estilos y plantilla
# ---------------------------------------------------------------------------
CSS = r"""
/* Layout: one reading column with a wide data band; tables scroll inside their own box. */
:root{
  --bg:#f3f6f8; --panel:#ffffff; --ink:#14212b; --muted:#566673; --line:#d6dee4;
  --cold:#2f6f9f; --hot:#c8531c; --accent:#0d5c63; --chip:#e6eef2; --good:#2c7a4b;
  --display:"Barlow Condensed","Arial Narrow",Arial,sans-serif;
  --body:"Source Sans 3","Segoe UI",Arial,sans-serif;
  --mono:"JetBrains Mono",ui-monospace,Menlo,Consolas,monospace;
}
@media (prefers-color-scheme: dark){:root:not([data-theme="light"]){
  --bg:#0f161c; --panel:#16212a; --ink:#e4ecf1; --muted:#9fb0bc; --line:#26343f;
  --cold:#6fb0e0; --hot:#f08a4b; --accent:#5cc3c9; --chip:#1f2d38; --good:#6cc48f; color-scheme:dark}}
:root[data-theme="dark"]{
  --bg:#0f161c; --panel:#16212a; --ink:#e4ecf1; --muted:#9fb0bc; --line:#26343f;
  --cold:#6fb0e0; --hot:#f08a4b; --accent:#5cc3c9; --chip:#1f2d38; --good:#6cc48f; color-scheme:dark}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--ink);font:17px/1.55 var(--body);}
a{color:var(--accent)} a:focus-visible,button:focus-visible,select:focus-visible,input:focus-visible{outline:3px solid var(--hot);outline-offset:2px}
.wrap{max-width:1120px;margin:0 auto;padding-left:max(16px,env(safe-area-inset-left,0px));padding-right:max(16px,env(safe-area-inset-right,0px))}
header.site{border-bottom:1px solid var(--line);background:var(--panel)}
header.site .wrap{display:flex;flex-wrap:wrap;gap:12px 24px;align-items:center;justify-content:space-between;padding-block:14px}
.brand{font:700 26px/1 var(--display);letter-spacing:.02em;text-transform:uppercase;color:var(--ink);text-decoration:none;display:flex;gap:10px;align-items:center}
.brand i{display:inline-block;width:22px;height:22px;border-radius:3px;background:linear-gradient(90deg,var(--cold) 0 50%,var(--hot) 50% 100%)}
nav.main{display:flex;flex-wrap:wrap;gap:6px 18px;font-weight:600}
nav.main a{color:var(--ink);text-decoration:none} nav.main a:hover{color:var(--accent)}
main{padding-block:28px 56px}
h1,h2,h3{font-family:var(--display);line-height:1.08;text-wrap:balance;margin:0}
h1{font-size:clamp(34px,6vw,56px);font-weight:700;letter-spacing:.005em}
h2{font-size:30px;font-weight:700;margin-top:40px} h3{font-size:22px;font-weight:600}
.lede{font-size:19px;color:var(--muted);max-width:62ch;margin:12px 0 0}
.crumbs{font:500 13px/1 var(--mono);letter-spacing:.06em;text-transform:uppercase;color:var(--muted);margin-bottom:12px}
.crumbs a{color:var(--muted)}
.stats{display:grid;grid-template-columns:repeat(auto-fit,minmax(170px,1fr));gap:12px;margin:24px 0 8px}
.stat{background:var(--panel);border:1px solid var(--line);border-radius:6px;padding:14px 16px}
.stat b{display:block;font:700 34px/1 var(--display);font-variant-numeric:tabular-nums}
.stat span{font-size:14px;color:var(--muted)}
.filters{display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));gap:10px;background:var(--panel);border:1px solid var(--line);border-radius:6px;padding:14px;margin-top:20px}
.filters label{display:flex;flex-direction:column;gap:4px;font:600 12px/1 var(--mono);letter-spacing:.06em;text-transform:uppercase;color:var(--muted)}
.filters input,.filters select{font:16px var(--body);padding:8px 10px;border:1px solid var(--line);border-radius:4px;background:var(--bg);color:var(--ink);min-width:0}
.count{margin:16px 0 8px;color:var(--muted);font-size:15px}
.jobs{display:flex;flex-direction:column;gap:8px;margin:0;padding:0;list-style:none}
.job{display:grid;grid-template-columns:minmax(0,1fr) 220px;gap:6px 20px;align-items:center;background:var(--panel);border:1px solid var(--line);border-radius:6px;padding:12px 16px}
.job .t{font-weight:700;font-size:17px;color:var(--ink);text-decoration:none} .job .t:hover{color:var(--accent)}
.job .meta{font-size:14px;color:var(--muted);display:flex;flex-wrap:wrap;gap:4px 12px}
.chip{display:inline-block;background:var(--chip);border-radius:3px;padding:1px 7px;font:500 12px/1.6 var(--mono);color:var(--ink)}
.chip.new{background:var(--good);color:var(--panel)}
.pay{font:600 15px/1.2 var(--mono);font-variant-numeric:tabular-nums;text-align:right}
.pay small{display:block;font:400 12px var(--body);color:var(--muted)}
.bar{position:relative;height:6px;border-radius:3px;background:var(--chip);margin-top:6px}
.bar span{position:absolute;top:0;bottom:0;border-radius:3px;background:linear-gradient(90deg,var(--cold),var(--hot))}
.nopay{color:var(--muted);font:400 13px var(--body)}
@media (max-width:640px){.job{grid-template-columns:1fr}.pay{text-align:left}}
.more{margin-top:14px;font:600 16px var(--body);padding:10px 18px;border-radius:4px;border:1px solid var(--accent);background:transparent;color:var(--accent);cursor:pointer}
.tablebox{overflow-x:auto;background:var(--panel);border:1px solid var(--line);border-radius:6px;margin-top:14px}
table{border-collapse:collapse;width:100%;font-size:15px;font-variant-numeric:tabular-nums}
th,td{padding:9px 12px;border-bottom:1px solid var(--line);text-align:left;white-space:nowrap}
th{font:600 12px/1.2 var(--mono);letter-spacing:.05em;text-transform:uppercase;color:var(--muted);background:var(--bg)}
td.num{text-align:right;font-family:var(--mono)} tr:last-child td{border-bottom:0}
.grid-links{display:grid;grid-template-columns:repeat(auto-fill,minmax(210px,1fr));gap:8px;margin-top:12px;padding:0;list-style:none}
.grid-links a{display:flex;justify-content:space-between;gap:8px;background:var(--panel);border:1px solid var(--line);border-radius:4px;padding:8px 12px;text-decoration:none;color:var(--ink)}
.grid-links a:hover{border-color:var(--accent)} .grid-links small{color:var(--muted);font-family:var(--mono)}
.note{font-size:14px;color:var(--muted);max-width:75ch}
.prose{max-width:68ch} .prose p,.prose li{font-size:18px}
.callout{border-left:4px solid var(--hot);background:var(--panel);padding:14px 18px;border-radius:0 6px 6px 0;margin-top:22px;max-width:75ch}
.signup{display:flex;flex-wrap:wrap;gap:8px;margin-top:10px}
.signup input{flex:1 1 220px;min-width:0;font:16px var(--body);padding:10px 12px;border:1px solid var(--line);border-radius:4px;background:var(--bg);color:var(--ink)}
.signup button{font:600 16px var(--body);padding:10px 18px;border:0;border-radius:4px;background:var(--hot);color:#fff;cursor:pointer}
footer.site{border-top:1px solid var(--line);color:var(--muted);font-size:14px}
footer.site .wrap{padding-block:22px;display:flex;flex-wrap:wrap;gap:8px 24px;justify-content:space-between}
@media (prefers-reduced-motion:reduce){*{transition:none!important}}
"""

FONTS = ('<link rel="preconnect" href="https://fonts.googleapis.com"><link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>'
         '<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Barlow+Condensed:wght@600;700'
         '&family=JetBrains+Mono:wght@400;500;600&family=Source+Sans+3:wght@400;600;700&display=swap">')


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
             + f'<header class="site"><div class="wrap"><a class="brand" href="{r("index.html")}"><i aria-hidden="true"></i>{E(SITE_NAME)}</a>{nav}</div></header>'
             + f'<main><div class="wrap">{body}</div></main>'
             + f'<footer class="site"><div class="wrap"><span>{E(SITE_NAME)} · {E(SITE_TAGLINE)}</span>'
             + f'<span>Pay ranges come from each employer\'s own posting. Updated {self.today:%B %-d, %Y}.</span></div></footer>'
             + ("" if bare else "</body></html>"))
        f = self.out / path
        f.parent.mkdir(parents=True, exist_ok=True)
        f.write_text(h, encoding="utf-8")
        self.pages.append(path)

    # -------------------------------------------------------------- pieces
    def job_row(self, j, depth: int, scale_max: float) -> str:
        title = clean_title(j["title"])
        loc = f'{j["city"]}, {j["state"]}'
        href = (self.rel(f'jobs/{j["slug"]}.html', depth) if not self.preview else j["url"])
        ext = "" if not self.preview else ' rel="noopener" target="_blank"'
        chips = f'<span class="chip">{E(ROLE_EN.get(j["role"], j["role"]))}</span>'
        if j["openings"] > 1:
            chips += f' <span class="chip">{j["openings"]} openings</span>'
        if j.get("days_posted") is not None and j["days_posted"] <= 7:
            chips += ' <span class="chip new">New</span>'
        if j["hourly_min"]:
            lo, hi = j["hourly_min"], j["hourly_max"] or j["hourly_min"]
            left, width = lo / scale_max * 100, max(2, (hi - lo) / scale_max * 100)
            pay = (f'<div class="pay">{money(lo)}–{money(hi)}<small>per hour'
                   + (f' · {money(j["pay_min"], "year")}–{money(j["pay_max"], "year")}/yr' if j["pay_unit"] == "year" else "")
                   + f'</small><div class="bar" aria-hidden="true"><span style="left:{left:.1f}%;width:{width:.1f}%"></span></div></div>')
        else:
            pay = '<div class="pay nopay">Pay not posted</div>'
        return (f'<li class="job"><div><a class="t" href="{E(href)}"{ext}>{E(title)}</a>'
                f'<div class="meta"><span>{E(j["company"])}</span><span>{E(loc)}</span>{chips}</div></div>{pay}</li>')

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
                '<p class="note">One email a week: the highest-paying new technician openings and one real number about pay or shifts. No spam.</p>'
                '<form class="signup" onsubmit="event.preventDefault();this.querySelector(\'button\').textContent=\'Thanks — you\\u2019re on the list\';">'
                '<label for="nl-email" class="note" style="flex-basis:100%">Email</label>'
                '<input id="nl-email" type="email" required placeholder="you@example.com" autocomplete="email">'
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
                 "hi": j["hourly_max"], "d": j["days_posted"],
                 "u": (f'jobs/{j["slug"]}.html' if not self.preview else j["url"])} for j in js]
        opts = lambda vals: "".join(f'<option value="{E(v)}">{E(v)}</option>' for v in vals)  # noqa: E731
        scale = max([j["hourly_max"] or 0 for j in js] + [1])
        body = (f'<h1>{E(SITE_TAGLINE)}.</h1>'
                f'<p class="lede">{total:,} open technician jobs at {len(companies)} data center operators, pulled straight from their own career pages. '
                f'{paid / total:.0%} show the pay range, and you can sort by it.</p>'
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
                '<label for="so">Sort<select id="so"><option value="pay">Highest pay</option><option value="new">Newest</option></select></label>'
                '</form><p class="count" id="cnt" aria-live="polite"></p><ul class="jobs" id="list"></ul>'
                '<button class="more" id="more" type="button">Show more jobs</button>'
                + self.signup()
                + f'<script>const J={json.dumps(data, separators=(",", ":"))};const SC={scale};'
                + r"""
const $=id=>document.getElementById(id);let N=40;
const esc=s=>String(s).replace(/[&<>"]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]));
const m=v=>'$'+v.toFixed(2);
function row(j){let pay='<div class="pay nopay">Pay not posted</div>';
 if(j.lo){const l=j.lo/SC*100,w=Math.max(2,(j.hi-j.lo)/SC*100);pay=`<div class="pay">${m(j.lo)}–${m(j.hi)}<small>per hour</small><div class="bar" aria-hidden="true"><span style="left:${l.toFixed(1)}%;width:${w.toFixed(1)}%"></span></div></div>`}
 const ext=/^https?:/.test(j.u)?' rel="noopener" target="_blank"':'';
 return `<li class="job"><div><a class="t" href="${esc(j.u)}"${ext}>${esc(j.t)}</a><div class="meta"><span>${esc(j.c)}</span><span>${esc(j.ci)}, ${j.s}</span><span class="chip">${esc(j.r)}</span>${j.n>1?`<span class="chip">${j.n} openings</span>`:''}${j.d!==null&&j.d<=7?'<span class="chip new">New</span>':''}</div></div>${pay}</li>`}
function draw(){const q=$('q').value.trim().toLowerCase(),st=$('st').value,co=$('co').value,ro=$('ro').value,p=parseFloat($('pay').value)||0,so=$('so').value;
 let r=J.filter(j=>(!q||(j.t+' '+j.ci).toLowerCase().includes(q))&&(!st||j.s===st)&&(!co||j.c===co)&&(!ro||j.r===ro)&&(!p||(j.hi||0)>=p));
 r.sort(so==='new'?(a,b)=>(a.d??999)-(b.d??999):(a,b)=>(b.hi||0)-(a.hi||0));
 const n=r.reduce((s,j)=>s+j.n,0);$('cnt').textContent=`${n.toLocaleString()} openings in ${r.length.toLocaleString()} listings`;
 $('list').innerHTML=r.slice(0,N).map(row).join('');$('more').hidden=r.length<=N}
['q','st','co','ro','pay','so'].forEach(id=>$(id).addEventListener('input',()=>{N=40;draw()}));
$('more').addEventListener('click',()=>{N+=40;draw()});draw();
</script>""")
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
        links = "".join(f'<li><a href="companies/{slug(c)}.html"><span>{E(c)}</span><small>{n:,}</small></a></li>'
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
        city_pages = {k for k, v in city_counts.items() if v >= MIN_CITY_OPENINGS}
        for s, n in states.items():
            name = STATE_NAMES.get(s, s)
            rows = [j for j in js if j["state"] == s]
            cities = Counter()
            for j in rows:
                cities[j["city"]] += j["openings"]
            c_links = "".join(
                (f'<li><a href="../cities/{slug(ci + "-" + s)}.html"><span>{E(ci)}</span><small>{k}</small></a></li>'
                 if (ci, s) in city_pages else f'<li><a href="#jobs"><span>{E(ci)}</span><small>{k}</small></a></li>')
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
                        f'<tr><th>First posted</th><td>{E(j["posted"] or "—")}</td></tr></tbody></table></div>'
                        f'<p><a class="more" href="{E(j["url"])}" rel="nofollow noopener" target="_blank">Apply on {E(j["company"])}\'s site</a></p>'
                        f'<h2>More {E(j["company"])} jobs in {E(STATE_NAMES.get(j["state"], j["state"]))}</h2>'
                        + self.job_list([x for x in js if x["company"] == j["company"] and x["state"] == j["state"] and x is not j], 1, 10)
                        + self.signup())
                self.page(f'jobs/{j["slug"]}.html', f'{clean_title(j["title"])} – {j["company"]}, {j["city"]} | {SITE_NAME}',
                          f'{clean_title(j["title"])} at {j["company"]} in {j["city"]}, {j["state"]}. Pay: {pay}.', body,
                          head_extra=f'<script type="application/ld+json">{json.dumps(ld)}</script>')

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
                  + (f'<p><a class="more" href="{E(SURVEY_URL)}" rel="noopener" target="_blank">Take the 2-minute survey</a></p>' if SURVEY_URL
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
