"""
Recolector de vacantes para técnicos de data center.

Fuentes públicas oficiales (las que las empresas publican para esto):
  - Amazon:     https://www.amazon.jobs/en/search.json  (+ página de cada vacante para el salario)
  - Greenhouse: https://boards-api.greenhouse.io/v1/boards/{board}/jobs?content=true
  - Ashby:      https://api.ashbyhq.com/posting-api/job-board/{org}?includeCompensation=true

Uso:
  python collector.py                 # recolecta en vivo y escribe data/jobs.csv y data/jobs.json
  python collector.py --from raw.json # procesa registros crudos ya descargados (sin internet)

Nunca recolecta de Indeed, LinkedIn ni otros agregadores: sus términos lo prohíben.
"""
from __future__ import annotations

import argparse
import csv
import html
import json
import re
import sys
import time
import urllib.parse
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from dataclasses import asdict, dataclass, field
from datetime import date, datetime
from pathlib import Path

# ---------------------------------------------------------------------------
# Configuración de fuentes. Para agregar una empresa, agrégala aquí.
# ---------------------------------------------------------------------------
GREENHOUSE_BOARDS = {"xai": "xAI", "coreweave": "CoreWeave"}
ASHBY_ORGS = {"crusoe": "Crusoe", "lambda": "Lambda"}
AMAZON_QUERIES = [
    "data center technician",
    "data center engineering operations",
    "data center operations",
    "critical environment",
    "data center facilities",
]
# Las fuentes son las páginas de empleo de las propias empresas: si la vacante sigue
# publicada ahí, sigue abierta. Por eso no se borran vacantes viejas por defecto; se
# guarda cuántos días lleva publicada para mostrarlo y filtrar en el sitio.
MAX_AGE_DAYS: int | None = None
USER_AGENT = "dc-tech-jobs-collector/0.1 (+contact: site owner)"

# Títulos que cuentan como "técnico" (operaciones e instalaciones críticas).
KEEP = re.compile(
    r"technician|\btech\b|electrician|operator|controls specialist|"
    r"critical (environment|facilit)|hvac|\bmechanic\b|chief engineer|"
    r"facilit(y|ies) (engineer|tech)|\bEOT\b|\bDCO\b",
    re.I,
)
DROP = re.compile(
    r"manager|director|software|scientist|recruit|program|product|account|sales|"
    r"\bintern\b|principal|architect|analyst|business|\bvp\b|head of|"
    # supervisión y construcción (no son técnicos de operación)
    r"superintendent|supervisor|foreman|commissioning (lead|engineer)|"
    # manufactura de fábrica (p. ej. plantas de Crusoe), no operación de data center
    r"\bcnc\b|press brake|assembly|quality|inspector|wiring technician|plant maintenance|"
    r"\bstaff\b|mechanical engineer|electrical engineer|internship|\bHRP\b|human resources partner",
    re.I,
)

US_STATES = {
    "AL": "Alabama", "AK": "Alaska", "AZ": "Arizona", "AR": "Arkansas", "CA": "California",
    "CO": "Colorado", "CT": "Connecticut", "DE": "Delaware", "DC": "District of Columbia",
    "FL": "Florida", "GA": "Georgia", "HI": "Hawaii", "ID": "Idaho", "IL": "Illinois",
    "IN": "Indiana", "IA": "Iowa", "KS": "Kansas", "KY": "Kentucky", "LA": "Louisiana",
    "ME": "Maine", "MD": "Maryland", "MA": "Massachusetts", "MI": "Michigan", "MN": "Minnesota",
    "MS": "Mississippi", "MO": "Missouri", "MT": "Montana", "NE": "Nebraska", "NV": "Nevada",
    "NH": "New Hampshire", "NJ": "New Jersey", "NM": "New Mexico", "NY": "New York",
    "NC": "North Carolina", "ND": "North Dakota", "OH": "Ohio", "OK": "Oklahoma", "OR": "Oregon",
    "PA": "Pennsylvania", "RI": "Rhode Island", "SC": "South Carolina", "SD": "South Dakota",
    "TN": "Tennessee", "TX": "Texas", "UT": "Utah", "VT": "Vermont", "VA": "Virginia",
    "WA": "Washington", "WV": "West Virginia", "WI": "Wisconsin", "WY": "Wyoming",
}
STATE_BY_NAME = {v.lower(): k for k, v in US_STATES.items()}

HOURS_PER_YEAR = 2080


@dataclass
class Job:
    source: str
    company: str
    job_id: str
    title: str
    city: str
    state: str          # código de 2 letras, vacío si no es EE.UU. o no se sabe
    location_raw: str
    posted: str         # YYYY-MM-DD
    url: str
    pay_min: float | None = None
    pay_max: float | None = None
    pay_unit: str = ""  # "hour" o "year"
    pay_text: str = ""
    level: str = ""     # I, II, III, IV o vacío
    role: str = ""      # categoría del puesto
    hourly_min: float | None = field(default=None)
    hourly_max: float | None = field(default=None)
    days_posted: int | None = field(default=None)  # días desde que se publicó
    openings: int = 1   # vacantes con el mismo puesto y ubicación (Amazon publica muchas iguales)


# ---------------------------------------------------------------------------
# Normalización
# ---------------------------------------------------------------------------
def is_tech_title(title: str) -> bool:
    return bool(KEEP.search(title)) and not DROP.search(title)


def classify_role(title: str) -> str:
    t = title.lower()
    if re.search(r"power generation|turbine|megapack|plant tech|generator", t):
        return "Energía / generación"
    if re.search(r"engineer(ing)? operations? tech|critical (environment|facilit)|facilit|chief engineer|"
                 r"\beot\b|\bdceo\b|command center|maint(enance)? tech|operations service", t):
        return "Instalaciones críticas"
    if re.search(r"\bit (support|services)\b|tech ops", t):
        return "Soporte TI"
    if re.search(r"infra ?-?delivery|\bid (flex|-)|decom|asset doc", t):
        return "Instalación / red"
    if "electric" in t:
        return "Eléctrico"
    if re.search(r"hvac|mechanic|chiller|plumbing|fluids", t):
        return "Mecánico / HVAC"
    if "controls" in t:
        return "Controles / BMS"
    if re.search(r"install|deploy|network|fiber|cabl|infra delivery", t):
        return "Instalación / red"
    if re.search(r"data ?cent(er|re)|\bdct\b|\bdco\b|server|hardware|linux", t):
        return "Técnico de data center (DCT)"
    if "operator" in t:
        return "Operador"
    return "Otro técnico"


_ROMAN = {"1": "I", "2": "II", "3": "III", "4": "IV", "i": "I", "ii": "II", "iii": "III", "iv": "IV"}


def classify_level(title: str) -> str:
    e = re.search(r"\b(?:engr|L)\s?([1-4])\b", title)  # Amazon: "DCEO Engr 4", "(L4)"
    if e:
        return _ROMAN[e.group(1)]
    m = re.search(r"\b(?:level|lvl|l)?\s*(iv|iii|ii|i|[1-4])\b(?!\.)", title, re.I)
    if m and re.search(r"(tech|technician|operator|engineer|electrician)\W*(?:level\s*)?" + re.escape(m.group(1)) + r"\b",
                       title, re.I):
        return _ROMAN[m.group(1).lower()]
    if re.search(r"\b(senior|sr\.?|lead)\b", title, re.I):
        return "III"
    if re.search(r"\b(junior|jr\.?|entry|apprentice|associate)\b", title, re.I):
        return "I"
    return ""


def parse_location(raw: str) -> tuple[str, str]:
    """Devuelve (ciudad, estado) para EE.UU.; ('','') si no se puede."""
    if not raw:
        return "", ""
    first = re.split(r"[;|]", raw)[0].strip()
    first = re.sub(r"\s*-\s*(US|USA|United States)$", "", first)  # "Arvada, CO - US"
    first = re.sub(r",(\S)", r", \1", first)                          # "Volo,IL"
    parts = [p.strip() for p in first.split(",") if p.strip()]
    state, city = "", ""
    for p in parts:
        if p.upper() in US_STATES and len(p) == 2:
            state = p.upper()
        elif p.lower() in STATE_BY_NAME:
            state = STATE_BY_NAME[p.lower()]
    if parts:
        cand = parts[0]
        if cand.upper() not in US_STATES and cand.lower() not in STATE_BY_NAME and cand.lower() not in {"usa", "us", "united states"}:
            city = cand
    return city, state


_PAY = re.compile(
    r"\$?\s*(\d[\d,]*(?:\.\d+)?)\s*(k)?\s*(?:-|–|—|to)\s*\$?\s*(\d[\d,]*(?:\.\d+)?)\s*(k)?"
    r"\s*(?:USD)?\s*(?:/|per|an|a)?\s*(hour|hr|hourly|year|yr|annually|annual|yearly)?",
    re.I,
)


def parse_pay(text: str) -> tuple[float | None, float | None, str]:
    if not text:
        return None, None, ""
    text = html.unescape(text)
    # "$65.000" (punto como separador de miles, error común en vacantes) -> "$65000"
    text = re.sub(r"(\d{1,3})\.(\d{3})(?!\d)", r"\1\2", text)
    for m in _PAY.finditer(text):
        if "$" not in m.group(0) and "USD" not in m.group(0).upper():
            continue  # sin símbolo de moneda no es salario ("24-48 horas")
        lo = float(m.group(1).replace(",", "")) * (1000 if m.group(2) else 1)
        hi = float(m.group(3).replace(",", "")) * (1000 if m.group(4) else 1)
        if hi < lo or lo <= 0:
            continue
        unit_word = (m.group(5) or "").lower()
        if unit_word.startswith(("h",)):
            unit = "hour"
        elif unit_word:
            unit = "year"
        else:
            unit = "hour" if hi < 300 else "year"
        # descartar números que no son salario (p. ej. "24-48 horas", años)
        if unit == "hour" and not (10 <= lo <= 250):
            continue
        if unit == "year" and not (20_000 <= lo <= 600_000):
            continue
        return lo, hi, unit
    return None, None, ""


def to_hourly(v: float | None, unit: str) -> float | None:
    if v is None:
        return None
    return round(v if unit == "hour" else v / HOURS_PER_YEAR, 2)


def finalize(job: Job) -> Job:
    if job.pay_min is None and job.pay_text:
        job.pay_min, job.pay_max, job.pay_unit = parse_pay(job.pay_text)
    job.hourly_min = to_hourly(job.pay_min, job.pay_unit)
    job.hourly_max = to_hourly(job.pay_max, job.pay_unit)
    job.level = classify_level(job.title)
    job.role = classify_role(job.title)
    if not job.state:
        job.city, job.state = parse_location(job.location_raw)
    return job


def parse_date(s: str) -> str:
    s = (s or "").strip()
    for fmt in ("%B %d, %Y", "%Y-%m-%d", "%Y-%m-%dT%H:%M:%S%z", "%Y-%m-%dT%H:%M:%S.%f%z"):
        try:
            return datetime.strptime(re.sub(r"\s+", " ", s), fmt).date().isoformat()
        except ValueError:
            continue
    m = re.match(r"(\d{4}-\d{2}-\d{2})", s)
    return m.group(1) if m else ""


def strip_html(s: str) -> str:
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", html.unescape(s or "")))


# ---------------------------------------------------------------------------
# Conversión de registros crudos de cada fuente a Job
# ---------------------------------------------------------------------------
def from_amazon(r: dict) -> Job:
    city, state = parse_location(r.get("loc", ""))
    pay = r.get("pay") or []
    lo = hi = None
    unit = ""
    if len(pay) == 3:
        lo, hi = float(str(pay[0]).replace(",", "")), float(str(pay[1]).replace(",", ""))
        unit = "hour" if str(pay[2]).lower().startswith("h") else "year"
    j = Job("amazon", "Amazon", str(r["id"]), re.sub(r"\s+,", ",", r["t"]).strip(" ,-"), city, state,
            r.get("loc", ""), parse_date(r.get("d", "")), "https://www.amazon.jobs" + r.get("path", ""),
            lo, hi, unit)
    j.openings = int(r.get("n", 1))
    return j


def from_greenhouse(board: str, company: str, r: dict) -> Job:
    loc = (r.get("location") or {}).get("name", "") if isinstance(r.get("location"), dict) else r.get("loc", "")
    pay_text = r.get("pay_text") or strip_html(r.get("content", ""))
    return Job("greenhouse", company, str(r["id"]), r["title"].strip(), "", "", loc,
               parse_date(r.get("first_published") or r.get("updated_at") or ""),
               r.get("absolute_url") or f"https://job-boards.greenhouse.io/{board}/jobs/{r['id']}",
               pay_text=pay_text)  # completo: el salario suele estar al final de la descripción


def from_ashby(org: str, company: str, r: dict) -> Job:
    loc = r.get("location", "") or ""
    pay_text = r.get("pay_text") or (r.get("compensation") or {}).get("compensationTierSummary", "") or ""
    return Job("ashby", company, str(r["id"]), r["title"].strip(), "", "", loc,
               parse_date(r.get("publishedAt", "")),
               r.get("jobUrl") or f"https://jobs.ashbyhq.com/{org}/{r['id']}", pay_text=pay_text)


def from_other(r: dict) -> Job:
    """Registro ya normalizado (Microsoft, Google, Workday): company, title, loc, posted, pay, url."""
    lo = hi = None
    unit = ""
    pay_text = ""
    p = r.get("pay")
    if isinstance(p, (list, tuple)) and len(p) == 3 and p[0]:
        lo, hi = float(str(p[0]).replace(",", "")), float(str(p[1]).replace(",", ""))
        unit = "hour" if str(p[2]).lower().startswith("h") else "year"
    elif isinstance(p, str):
        pay_text = p
    return Job(r.get("source", "other"), r["company"], r.get("id") or r["url"], r["title"].strip(), "", "",
               r.get("loc", ""), parse_date(r.get("posted", "")), r["url"], lo, hi, unit, pay_text=pay_text)


# ---------------------------------------------------------------------------
# Descarga en vivo
# ---------------------------------------------------------------------------
def get(url: str, as_json: bool = True):
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(req, timeout=30) as resp:
        body = resp.read().decode("utf-8", "replace")
    return json.loads(body) if as_json else body


def fetch_amazon() -> list[dict]:
    seen: dict[str, dict] = {}
    for q in AMAZON_QUERIES:
        for off in range(0, 2000, 100):
            url = ("https://www.amazon.jobs/en/search.json?" + urllib.parse.urlencode(
                {"base_query": q, "result_limit": 100, "offset": off, "country": "USA"}))
            jobs = get(url).get("jobs", [])
            for j in jobs:
                seen[j.get("id_icims") or j["id"]] = {
                    "id": j.get("id_icims"), "path": j["job_path"], "t": j["title"],
                    "loc": j.get("normalized_location") or j.get("location", ""), "d": j.get("posted_date", "")}
            if len(jobs) < 100:
                break
            time.sleep(0.5)
    techs = [r for r in seen.values() if is_tech_title(r["t"])]
    # Amazon publica muchas vacantes idénticas (mismo puesto y ciudad). Se agrupan en una sola fila
    # con el número de vacantes, y solo se descarga el pago de una por grupo.
    groups: dict[tuple, list[dict]] = {}
    for r in techs:
        groups.setdefault((r["t"].strip().lower(), r["loc"].strip().lower()), []).append(r)
    reps = []
    for rows in groups.values():
        rows.sort(key=lambda r: parse_date(r.get("d", "")) or "", reverse=True)
        rep = dict(rows[0])
        rep["n"] = len(rows)
        reps.append(rep)
    pay_re = re.compile(r"(\d[\d,]*\.?\d*)\s*-\s*(\d[\d,]*\.?\d*)\s*USD\s*(hourly|annually|annual|yearly)", re.I)

    def add_pay(r):
        r["pay"] = None
        for intento in range(4):  # Amazon a veces responde "Server Busy": reintentar con espera
            try:
                page = strip_html(get("https://www.amazon.jobs" + r["path"], as_json=False))
                m = pay_re.search(page)
                if m:
                    r["pay"] = list(m.groups())
                    return r
                if "Server Busy" not in page:
                    return r
            except Exception:
                pass
            time.sleep(2 * (intento + 1))
        return r

    with ThreadPoolExecutor(max_workers=3) as ex:
        return list(ex.map(add_pay, reps))


def fetch_greenhouse(board: str) -> list[dict]:
    data = get(f"https://boards-api.greenhouse.io/v1/boards/{board}/jobs?content=true")
    return [j for j in data.get("jobs", []) if is_tech_title(j.get("title", ""))]


def fetch_ashby(org: str) -> list[dict]:
    data = get(f"https://api.ashbyhq.com/posting-api/job-board/{org}?includeCompensation=true")
    return [j for j in data.get("jobs", []) if is_tech_title(j.get("title", ""))]


# Workday: (empresa, host, tenant, sitio). Sus páginas de empleo usan este API público.
WORKDAY_SITES = [("Equinix", "equinix.wd1.myworkdayjobs.com", "equinix", "External")]
WORKDAY_QUERIES = ["technician", "engineer", "data center", "facilities", "operations"]
# Ciudades de Workday sin estado -> estado (Workday a veces solo da la ciudad)
CITY_STATE = {"Englewood": "CO", "Sunnyvale": "CA", "Culpeper": "VA", "San Jose": "CA", "Torrance": "CA",
              "Boca Raton": "FL", "Ashburn": "VA", "Dallas": "TX", "El Segundo": "CA", "Secaucus": "NJ",
              "Palo Alto": "CA", "Silicon Valley": "CA"}


def post_json(url: str, payload: dict):
    req = urllib.request.Request(url, data=json.dumps(payload).encode(), method="POST",
                                 headers={"User-Agent": USER_AGENT, "Content-Type": "application/json",
                                          "Accept": "application/json"})
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.loads(resp.read().decode("utf-8", "replace"))


def fetch_workday(company: str, host: str, tenant: str, site: str) -> list[dict]:
    base = f"https://{host}/wday/cxs/{tenant}/{site}"
    seen: dict[str, dict] = {}
    for q in WORKDAY_QUERIES:
        for off in range(0, 1000, 20):
            r = post_json(base + "/jobs", {"appliedFacets": {}, "limit": 20, "offset": off, "searchText": q})
            posts = r.get("jobPostings", [])
            for p in posts:
                if p.get("externalPath"):
                    seen[p["externalPath"]] = p
            if len(posts) < 20:
                break
            time.sleep(0.3)
    out = []
    for path, p in seen.items():
        if not is_tech_title(p.get("title", "")):
            continue
        info = get(base + path).get("jobPostingInfo", {})
        if "United States" not in ((info.get("country") or {}).get("descriptor") or "United States"):
            continue
        desc = strip_html(info.get("jobDescription", ""))
        m = re.search(r"([\d,]+(?:\.\d+)?)\s*-\s*([\d,]+(?:\.\d+)?)\s*USD\s*/\s*(Annual|Hourly|Year|Hour)", desc, re.I)
        pay = f"${m.group(1)} - ${m.group(2)} per {'hour' if 'hour' in m.group(3).lower() else 'year'}" if m else desc
        city = re.sub(r"^[A-Z]{2}\d+\w*\s+", "", info.get("location") or p.get("locationsText", ""))
        loc = f"{city}, {CITY_STATE[city]}" if city in CITY_STATE else city
        out.append({"company": company, "title": p["title"], "loc": loc, "posted": info.get("startDate", ""),
                    "pay": pay, "url": info.get("externalUrl") or f"https://{host}/{site}{path}",
                    "id": info.get("jobReqId") or path, "source": "workday"})
    return out


def fetch_microsoft() -> list[dict]:
    base = "https://apply.careers.microsoft.com/api/pcsx"
    seen: dict = {}
    for q in ["datacenter", "data center", "critical environment", "datacenter technician", "critical facilities"]:
        for start in range(0, 600, 10):
            r = get(f"{base}/search?" + urllib.parse.urlencode(
                {"domain": "microsoft.com", "query": q, "location": "United States", "start": start}))
            pos = (r.get("data") or {}).get("positions", [])
            for p in pos:
                seen[p["id"]] = p
            if len(pos) < 10:
                break
    out = []
    for p in seen.values():
        if not is_tech_title(p["name"]):
            continue
        d = get(f"{base}/position_details?position_id={p['id']}&domain=microsoft.com&hl=en").get("data", {})
        loc = ((p.get("standardizedLocations") or p.get("locations") or [""])[0]).replace(", US", "")
        out.append({"company": "Microsoft", "title": p["name"], "loc": loc,
                    "posted": datetime.utcfromtimestamp(p["postedTs"]).date().isoformat(),
                    "pay": strip_html(d.get("jobDescription", "")),
                    "url": "https://apply.careers.microsoft.com" + p["positionUrl"], "id": str(p["id"]),
                    "source": "microsoft"})
    return out


def fetch_google() -> list[dict]:
    base = "https://www.google.com/about/careers/applications/jobs/results"
    ids: dict = {}
    for q in ['"data center"', '"critical facilities"']:
        for page in range(1, 31):
            h = get(f"{base}?" + urllib.parse.urlencode({"q": q, "location": "United States", "page": page}), as_json=False)
            before = len(ids)
            for jid, sl in re.findall(r"jobs/results/(\d+)-([a-z0-9-]+)", h):
                ids[jid] = sl
            if len(ids) == before:
                break
    out = []
    for jid, sl in ids.items():
        if not is_tech_title(sl.replace("-", " ")):
            continue
        h = get(f"{base}/{jid}-{sl}", as_json=False)
        t = strip_html(re.sub(r"<script[\s\S]*?</script>|<style[\s\S]*?</style>", " ", h))
        k = t.rfind("Back to jobs search ")
        title = re.split(r" share Share", t[k + 20:])[0].strip() if k >= 0 else sl.replace("-", " ").title()
        loc = (re.search(r"corporate_fare Google place (.*?) bar_chart", t) or [None, ""])[1].split(";")[0]
        m = re.search(r"US: \$([\d,]+) - \$([\d,]+) \(USD\)", h)
        out.append({"company": "Google", "title": title, "loc": loc.replace(", USA", ""), "posted": "",
                    "pay": [m.group(1), m.group(2), "year"] if m else None,
                    "url": f"{base}/{jid}-{sl}", "id": jid, "source": "google"})
    return out


def collect_live() -> dict:
    raw = {"amazon": [], "greenhouse": {}, "ashby": {}, "other": []}
    try:
        raw["amazon"] = fetch_amazon()
    except Exception as e:  # una fuente caída no debe tumbar todo
        print("aviso: amazon", e, file=sys.stderr)
    for b in GREENHOUSE_BOARDS:
        try:
            raw["greenhouse"][b] = fetch_greenhouse(b)
        except Exception as e:
            print("aviso: greenhouse", b, e, file=sys.stderr)
    for o in ASHBY_ORGS:
        try:
            raw["ashby"][o] = fetch_ashby(o)
        except Exception as e:
            print("aviso: ashby", o, e, file=sys.stderr)
    for fn in (fetch_microsoft, fetch_google):
        try:
            raw["other"] += fn()
        except Exception as e:  # una fuente caída no debe tumbar todo
            print("aviso:", fn.__name__, e, file=sys.stderr)
    for args in WORKDAY_SITES:
        try:
            raw["other"] += fetch_workday(*args)
        except Exception as e:
            print("aviso: workday", args[0], e, file=sys.stderr)
    return raw


# ---------------------------------------------------------------------------
# Proceso principal
# ---------------------------------------------------------------------------
def build(raw: dict, today: date, max_age_days: int | None = MAX_AGE_DAYS, us_only: bool = True) -> list[Job]:
    jobs: list[Job] = []
    for r in raw.get("amazon", []):
        if is_tech_title(r["t"]):
            jobs.append(from_amazon(r))
    for board, rows in raw.get("greenhouse", {}).items():
        for r in rows:
            if is_tech_title(r["title"]):
                jobs.append(from_greenhouse(board, GREENHOUSE_BOARDS.get(board, board), r))
    for org, rows in raw.get("ashby", {}).items():
        for r in rows:
            if is_tech_title(r["title"]):
                jobs.append(from_ashby(org, ASHBY_ORGS.get(org, org), r))
    for r in raw.get("other", []):
        if is_tech_title(r["title"]):
            jobs.append(from_other(r))

    out, seen = [], set()
    for j in map(finalize, jobs):
        key = (j.company, j.job_id)
        if key in seen:
            continue
        seen.add(key)
        if us_only and not j.state:
            continue
        if j.posted:
            j.days_posted = (today - date.fromisoformat(j.posted)).days
            if max_age_days is not None and j.days_posted > max_age_days:
                continue
        out.append(j)
    out.sort(key=lambda j: (j.posted or ""), reverse=True)
    return out


def write_outputs(jobs: list[Job], outdir: Path) -> None:
    outdir.mkdir(parents=True, exist_ok=True)
    cols = ["company", "title", "role", "level", "city", "state", "openings", "posted", "days_posted",
            "hourly_min", "hourly_max", "pay_min", "pay_max", "pay_unit", "url", "source", "job_id"]
    with open(outdir / "jobs.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=cols, extrasaction="ignore")
        w.writeheader()
        for j in jobs:
            w.writerow(asdict(j))
    with open(outdir / "jobs.json", "w", encoding="utf-8") as f:
        json.dump([{k: v for k, v in asdict(j).items() if k != "pay_text"} for j in jobs], f,
                  ensure_ascii=False, indent=1)


def keep_previous_if_source_failed(jobs: list[Job], prev_path: Path, today: date) -> list[Job]:
    """Si una empresa que ayer tenía vacantes hoy trae 0 (fuente caída o bloqueada),
    conserva sus vacantes de ayer para no publicar un sitio a medias."""
    if not prev_path.exists():
        return jobs
    try:
        prev = json.loads(prev_path.read_text(encoding="utf-8"))
    except Exception:
        return jobs
    live = {j.company for j in jobs}
    names = set(Job.__dataclass_fields__)
    kept = []
    for d in prev:
        if d.get("company") in live:
            continue
        j = Job(**{k: v for k, v in d.items() if k in names})
        if j.posted:
            j.days_posted = (today - date.fromisoformat(j.posted)).days
        kept.append(j)
    if kept:
        print(f"aviso: se conservan {len(kept)} vacantes de ayer de: "
              + ", ".join(sorted({j.company for j in kept})), file=sys.stderr)
    out = jobs + kept
    out.sort(key=lambda j: (j.posted or ""), reverse=True)
    return out


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--from", dest="src", help="archivo JSON con registros crudos")
    ap.add_argument("--out", default="data")
    ap.add_argument("--today", help="fecha de referencia YYYY-MM-DD (por defecto hoy)")
    ap.add_argument("--max-age", type=int, default=MAX_AGE_DAYS,
                    help="opcional: descartar vacantes publicadas hace más de N días")
    a = ap.parse_args(argv)
    raw = json.loads(Path(a.src).read_text()) if a.src else collect_live()
    today = date.fromisoformat(a.today) if a.today else date.today()
    jobs = build(raw, today, a.max_age)
    if not a.src:
        jobs = keep_previous_if_source_failed(jobs, Path(a.out) / "jobs.json", today)
    write_outputs(jobs, Path(a.out))
    print(f"{len(jobs)} vacantes de técnico en EE.UU. -> {a.out}/jobs.csv")
    return 0


if __name__ == "__main__":
    sys.exit(main())
