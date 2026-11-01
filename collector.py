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
import urllib.error
import urllib.parse
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from dataclasses import asdict, dataclass, field
from datetime import date, datetime
from pathlib import Path

# ---------------------------------------------------------------------------
# Configuración de fuentes. Para agregar una empresa, agrégala aquí.
# ---------------------------------------------------------------------------
GREENHOUSE_BOARDS = {"align46": "Align", "xai": "xAI", "coreweave": "CoreWeave", "nebius": "Nebius", "holderconstruction": "Holder Construction",
                     "tds": "TDS (Total Deployment Solutions)", "compudynamics": "Compu Dynamics"}
# Lever: org -> empresa. Las contratistas de telecom también publican fibra/torres; DC_ONLY las limita a data center.
LEVER_ORGS = {"networkconnex": "Network Connex", "cologix": "Cologix", "midtechgroup": "MidPoint Technology Group"}
DC_ONLY = {"Network Connex", "AFL", "Align"}
DC_TITLE = re.compile(r"data ?cent|\bISP\b|\bDC\b|low voltage|structured cabl|white space", re.I)
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
    r"facilit(y|ies) (engineer|tech)|\bEOT\b|\bDCO\b|"
    # contratistas de despliegue: la carrera del técnico sigue en lead/foreman de cuadrilla
    r"deployment (lead|foreman)|field lead|lead data center|\binstaller\b|network specialist|\bsplicer\b",
    re.I,
)
DROP = re.compile(
    r"manager|director|software|scientist|recruit|program|product|account|sales|"
    r"\bintern\b|principal|architect|analyst|business|\bvp\b|head of|"
    # supervisión y construcción (no son técnicos de operación)
    r"superintendent|supervisor|foreman|commissioning (lead|engineer)|"
    # manufactura de fábrica (p. ej. plantas de Crusoe), no operación de data center
    r"\bcnc\b|press brake|assembly|quality|inspector|wiring technician|plant maintenance|"
    r"\bstaff\b|mechanical engineer|electrical engineer|internship|\bHRP\b|human resources partner|"
    r"instructional|designer|trainer|coordinator",
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
    desc: str = ""      # descripción completa (no se guarda; sirve para detectar per diem, hospedaje, etc.)
    perks: str = ""     # beneficios detectados, separados por "|": per_diem, housing, travel, rotation:3/1, overtime, ...
    per_diem: float | None = None  # monto diario del per diem si lo dicen
    entry: bool = False  # apto para principiantes (nivel I / sin experiencia, según título o descripción)
    last_seen: str = ""  # última fecha en que la fuente la mostró; las conservadas de ayer caducan a los 5 días


# ---------------------------------------------------------------------------
# Normalización
# ---------------------------------------------------------------------------
def is_tech_title(title: str) -> bool:
    if re.search(r"deployment foreman|foreman.*data ?cent|data ?cent.*foreman|electrical (general )?foreman", title, re.I):
        return True  # en contratistas, foreman de cuadrilla es el siguiente paso del técnico
    return bool(KEEP.search(title)) and not DROP.search(title)


def classify_role(title: str) -> str:
    t = title.lower()
    if re.search(r"power generation|turbine|megapack|plant tech|generator", t):
        return "Energía / generación"
    if re.search(r"engineer(ing)? operations? tech|critical (environment|facilit|operations)|facilit|chief engineer|"
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
    if re.search(r"install|deploy|network|fiber|cabl|splic|infra delivery", t):
        return "Instalación / red"
    if re.search(r"field engineer tech|engineer technician", t):
        return "Construcción"
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


PERK_RULES = [
    ("per_diem", re.compile(r"per[ -]?diem|\bperdiem\b|daily allowance|meal allowance|M&IE", re.I)),
    ("housing", re.compile(r"housing (is )?(provided|included|paid|available|covered|offered)|(company|employer)[- ]paid (housing|lodging|hotel)|"
                           r"lodging (provided|included|paid|covered)|hotel (provided|paid|included|covered)|free (housing|lodging)|"
                           r"housing (allowance|stipend)|lodging (allowance|stipend)|provided housing|furnished housing|corporate housing", re.I)),
    ("travel", re.compile(r"\btravel(ing|ling)? (position|role|job|crew|technician|required|is required|is a requirement|assignment)|\d{2,3}\s?% travel|"
                          r"nationwide travel|extensive travel|must be (able|willing) to travel|willing to travel|travel (up to|across|to project|away from home)|"
                          r"travel (may be |will be |is )?required|^travel\b", re.I)),
    ("overtime", re.compile(r"\bovertime\b|\bOT\b|time and a half|\d{2}\+?\s?(hours|hrs)\s?(per|a|/)\s?(week|wk)|\b[56]\s?x\s?1[02]\b", re.I)),
    ("signon", re.compile(r"sign[- ]?on bonus|signing bonus|hiring bonus", re.I)),
    ("relocation", re.compile(r"relocation (assistance|package|bonus|support|available|provided)", re.I)),
    ("shift_diff", re.compile(r"shift differential|night differential|night shift premium", re.I)),
    ("vehicle", re.compile(r"company (vehicle|truck|van)|vehicle (allowance|stipend)|truck allowance|mileage reimburse", re.I)),
    ("retention", re.compile(r"retention bonus|completion bonus|project bonus", re.I)),
]
PER_DIEM_AMOUNT = re.compile(r"(?:per[ -]?diem[^$\n]{0,40}\$\s?(\d{2,3})(?:\.\d\d)?\s*(?:/|per|a|each)?\s*(?:day|daily|diem)?)|"
                             r"(?:\$\s?(\d{2,3})(?:\.\d\d)?\s*(?:/|per|a)\s*(?:day|diem)\b[^.\n]{0,40}per[ -]?diem)|"
                             r"(?:\$\s?(\d{2,3})(?:\.\d\d)?\s*(?:/|per|a)?\s*(?:day|daily)\s+per[ -]?diem)|"
                             r"(?:per[ -]?diem\s*(?:of|:|-|–|is|at)?\s*\$\s?(\d{2,3}))", re.I)
SHIFT_HOURS = re.compile(r"\b(1[02])[- ]?(?:hour|hr)s?\s*(?:shift|day|schedule|work ?day)s?|\b(1[02])s\b(?! ?%)|\b([56])\s?x\s?(1[02])s?\b", re.I)
DAYS_WEEK = re.compile(r"\b([5-7])\s*(?:days?|days a|days per|days/)\s*(?:a |per |/)?\s*(?:week|wk)\b|\bmonday\s*(?:-|to|through|thru)\s*(saturday|sunday)\b", re.I)
HOURS_WEEK = re.compile(r"\b([4-8]\d)\+?\s*(?:hours|hrs)\s*(?:per|a|/)\s*(?:week|wk)\b", re.I)
ROTATION = re.compile(r"(\d{1,2})\s*(weeks?|wks?|days?)?\s*(?:on|-on)\s*(?:/|,|and|&)?\s*(\d{1,2})\s*(weeks?|wks?|days?)?\s*(?:off|-off)", re.I)


def extract_perks(text: str) -> tuple[str, float | None]:
    """Detecta beneficios de viaje en la descripción: per diem (y monto), hospedaje, rotación, horas extra, bonos."""
    text = strip_html(text or "")
    if not text:
        return "", None
    tags = [name for name, rx in PERK_RULES if rx.search(text)]
    per_diem = None
    m = PER_DIEM_AMOUNT.search(text)
    if m:
        amt = float(next(g for g in m.groups() if g))
        if 30 <= amt <= 400:
            per_diem = amt
            if "per_diem" not in tags:
                tags.insert(0, "per_diem")
    hours = days = None
    nxm = [(int(a), int(b)) for a, b in re.findall(r"\b([56])\s?x\s?(1[02])s?\b", text, re.I)]  # "6x12": días x horas
    if nxm:  # si ofrecen varias ("6x10 or 6x12"), se muestra la más larga
        days, hours = max(nxm, key=lambda t: t[0] * t[1])
        days, hours = str(days), str(hours)
    else:
        sh = SHIFT_HOURS.search(text)
        hours = next((g for g in sh.groups() if g), None) if sh else None
        dw = DAYS_WEEK.search(text)
        days = (dw.group(1) or {"saturday": "6", "sunday": "7"}[dw.group(2).lower()]) if dw else None
    hw = HOURS_WEEK.search(text)
    sched = []
    if hours:
        sched.append(f"{hours}h")
    if days:
        sched.append(f"{days}d")
    if hw and not (hours and days):
        sched.append(f"{hw.group(1)}hw")
    if sched:
        tags.append("schedule:" + "/".join(sched))
    r = ROTATION.search(text)
    if r and (r.group(2) or r.group(4)):
        on, off = int(r.group(1)), int(r.group(3))
        if 1 <= on <= 60 and 1 <= off <= 30:
            tags.append(f"rotation:{on}/{off}")
    return "|".join(tags), per_diem


ENTRY_TITLE = re.compile(r"entry[- ]level|\bentry\b|associate|apprentice|junior|trainee|helper|cable puller|\btech(nician)? (1|i)\b|"
                         r"\blevel (1|i)\b|\bl1\b|\btier (1|i)\b|\b(1|i)\s*[-–]|no experience", re.I)
ENTRY_DESC = re.compile(r"no (prior |previous )?experience (is )?(required|necessary|needed)|entry[- ]level|will train|paid training|"
                        r"on[- ]the[- ]job training|\b0\s*[-–]\s*[12]\+? years|zero experience|new to the (industry|trade|field)|"
                        r"high school diploma or (equivalent|ged)", re.I)
NOT_ENTRY = re.compile(r"senior|\bsr\b|lead|foreman|supervisor|manager|superintendent|\biii\b|\biv\b|\b[3-5]\b|specialist|engineer\b|journeyman|master", re.I)


def is_entry(title: str, level: str, text: str) -> bool:
    if NOT_ENTRY.search(title) or level in ("III", "IV"):
        return False
    if level == "I" or ENTRY_TITLE.search(title):
        return True
    return bool(ENTRY_DESC.search(text or "")) and level != "II"


def finalize(job: Job) -> Job:
    job.entry = is_entry(job.title, classify_level(job.title), job.desc or job.pay_text)
    if job.pay_min is None and job.pay_text:
        job.pay_min, job.pay_max, job.pay_unit = parse_pay(job.pay_text)
    if not job.perks:
        job.perks, job.per_diem = extract_perks(job.desc or job.pay_text)
        if re.search(r"\btravel(ing)?\b", job.title, re.I) and "travel" not in job.perks.split("|"):
            job.perks = "|".join(x for x in ["travel", job.perks] if x)
    job.desc = ""
    job.hourly_min = to_hourly(job.pay_min, job.pay_unit)
    job.hourly_max = to_hourly(job.pay_max, job.pay_unit)
    job.level = classify_level(job.title)
    job.role = classify_role(job.title)
    if not job.state:
        job.city, job.state = parse_location(job.location_raw)
    return job


def parse_date(s: str) -> str:
    s = (s or "").strip()
    for fmt in ("%B %d, %Y", "%b %d, %Y", "%Y-%m-%d", "%Y-%m-%dT%H:%M:%S%z", "%Y-%m-%dT%H:%M:%S.%f%z"):
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
        ok = (10 <= lo <= 250) if unit == "hour" else (20_000 <= lo <= 600_000)
        if not ok or hi < lo:  # p. ej. "$0.02 - $0.03": un error en la publicación, no un salario
            lo = hi = None
            unit = ""
    elif isinstance(p, str):
        pay_text = p
    return Job(r.get("source", "other"), r["company"], r.get("id") or r["url"], r["title"].strip(), "", "",
               r.get("loc", ""), parse_date(r.get("posted", "")), r["url"], lo, hi, unit, pay_text=pay_text,
               desc=r.get("desc") or "")


# ---------------------------------------------------------------------------
# Descarga en vivo
# ---------------------------------------------------------------------------
def get(url: str, as_json: bool = True):
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    for intento in range(4):
        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                body = resp.read().decode("utf-8", "replace")
            return json.loads(body) if as_json else body
        except urllib.error.HTTPError as e:
            # 429 = demasiadas peticiones, 5xx = servidor caído: esperar y reintentar
            if e.code not in (429, 500, 502, 503, 504) or intento == 3:
                raise
            time.sleep(8 * (intento + 1))
    raise RuntimeError("sin respuesta")  # no se llega aquí


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


# Constructoras: solo los puestos de obra con pago por hora que son camino de entrada para técnicos
BUILDER_KEEP = {"holderconstruction": re.compile(r"field engineer technician|engineer technician|energy marshall", re.I)}


def fetch_greenhouse(board: str) -> list[dict]:
    data = get(f"https://boards-api.greenhouse.io/v1/boards/{board}/jobs?content=true")
    keep = BUILDER_KEEP.get(board)
    return [j for j in data.get("jobs", [])
            if (keep.search(j.get("title", "")) if keep else is_tech_title(j.get("title", "")))]


def fetch_rosendin() -> list[dict]:
    """Rosendin (contratista eléctrico): su sitio WordPress expone las vacantes por admin-ajax."""
    req = urllib.request.Request("https://www.rosendin.com/wp-admin/admin-ajax.php",
                                 data=b"action=openings_listing&per_page=1000&page=1",
                                 headers={"User-Agent": USER_AGENT, "Content-Type": "application/x-www-form-urlencoded"})
    with urllib.request.urlopen(req, timeout=30) as resp:
        posts = json.loads(resp.read().decode("utf-8", "replace")).get("posts", [])
    out = []
    for r in posts:
        title = (r.get("title") or "").strip()
        if r.get("category") != "Field" or not re.search(r"electrician|journeyman|foreman", title, re.I):
            continue
        out.append({"company": "Rosendin", "title": title, "loc": r.get("location", ""), "posted": "",
                    "pay": None, "url": r.get("url", ""), "id": "rosendin-" + str(r.get("id")), "source": "rosendin"})
    return out


def fetch_ashby(org: str) -> list[dict]:
    data = get(f"https://api.ashbyhq.com/posting-api/job-board/{org}?includeCompensation=true")
    return [j for j in data.get("jobs", []) if is_tech_title(j.get("title", ""))]


# Workday: (empresa, host, tenant, sitio). Sus páginas de empleo usan este API público.
WORKDAY_SITES = [("Equinix", "equinix.wd1.myworkdayjobs.com", "equinix", "External"),
                 ("QTS", "qtsdatacenters.wd5.myworkdayjobs.com", "qtsdatacenters", "qts")]
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
        m2 = re.match(r"^US ([A-Z]{2}) (.+?)(?: \d+)?(?: DC\d+)?$", city)  # QTS: "US TX Turkey 1 DC1"
        if m2:
            city = f"{m2.group(2)}, {m2.group(1)}"
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


# ---------------------------------------------------------------------------
# Lever (Network Connex, Cologix)
# ---------------------------------------------------------------------------
def fetch_lever(org: str, company: str) -> list[dict]:
    rows = get(f"https://api.lever.co/v0/postings/{org}?mode=json")
    out = []
    for r in rows:
        title = (r.get("text") or "").strip()
        team = (r.get("categories") or {}).get("team", "") or ""
        if not is_tech_title(title):
            continue
        # contratistas: solo data center, por título o por el equipo que la empresa asigna
        if company in DC_ONLY and not (DC_TITLE.search(title) or ("data center" in team.lower() and not re.search(r"\bOSP\b|splic", title, re.I))):
            continue
        sr = r.get("salaryRange") or {}
        pay = None
        if sr.get("min") and sr.get("max"):
            unit = "hour" if "hour" in str(sr.get("interval", "")) else "year"
            pay = [sr["min"], sr["max"], unit]
        else:
            pay = r.get("descriptionPlain") or ""
        posted = ""
        if r.get("createdAt"):
            posted = datetime.utcfromtimestamp(r["createdAt"] / 1000).strftime("%Y-%m-%d")
        out.append({"company": company, "title": title, "loc": (r.get("categories") or {}).get("location", ""),
                    "posted": posted, "pay": pay, "url": r.get("hostedUrl", ""), "id": r.get("id"), "source": "lever",
                    "desc": (r.get("descriptionPlain") or "") + " " + " ".join(
                        strip_html(l.get("text", "") + " " + l.get("content", "")) for l in (r.get("lists") or []))})
    return out


# ---------------------------------------------------------------------------
# Introl (tarjetas en el HTML de introl.com/careers)
# ---------------------------------------------------------------------------
INTROL_CARD = re.compile(
    r'<a href="([^"]+)"[^>]*class="job-card[^"]*"[^>]*>.*?<h3 class="job-title">(.*?)</h3>\s*'
    r'<p class="job-location">(.*?)</p>(.*?)</a>', re.S)


def parse_introl(html_text: str) -> list[dict]:
    out = []
    for url, title, loc, rest in INTROL_CARD.findall(html_text):
        title = html.unescape(title).strip()
        if not is_tech_title(title):
            continue
        m = re.search(r'job-salary">(.*?)<', rest)
        pay = html.unescape(m.group(1)).strip() if m else ""
        jid = url.rstrip("/").rsplit("/", 1)[-1]
        out.append({"company": "Introl", "title": title, "loc": html.unescape(loc).strip(), "posted": "",
                    "pay": pay, "url": url, "id": "introl-" + jid, "source": "introl"})
    return out


def fetch_introl() -> list[dict]:
    return parse_introl(get("https://introl.com/careers", as_json=False))


# ---------------------------------------------------------------------------
# AFL (Phenom People: el JSON de resultados viene dentro del HTML)
# ---------------------------------------------------------------------------
def parse_phenom(html_text: str) -> tuple[list[dict], int]:
    i = html_text.find("phApp.ddo")
    if i < 0:
        return [], 0
    j = html_text.find("{", i)
    data, _ = json.JSONDecoder().raw_decode(html_text[j:])
    e = data.get("eagerLoadRefineSearch") or {}
    return (e.get("data") or {}).get("jobs") or [], int(e.get("totalHits") or 0)


def fetch_afl() -> list[dict]:
    base = "https://careers.aflglobal.com/us/en/search-results?keywords=data%20center"
    seen, out = set(), []
    start, total = 0, 1
    while start < total and start < 400:
        jobs, total = parse_phenom(get(f"{base}&from={start}&s=1", as_json=False))
        if not jobs:
            break
        for r in jobs:
            title = (r.get("title") or "").strip()
            jid = r.get("jobId") or r.get("reqId")
            if jid in seen or not is_tech_title(title):
                continue
            seen.add(jid)
            if not (DC_TITLE.search(title) or DC_TITLE.search(r.get("descriptionTeaser") or "")):
                continue
            url = r.get("applyUrl") or r.get("jobUrl") or ""
            if url.startswith("/"):
                url = "https://careers.aflglobal.com" + url
            out.append({"company": "AFL", "title": title, "loc": f"{r.get('city', '')}, {r.get('state', '')}",
                        "posted": (r.get("postedDate") or "")[:10], "pay": (r.get("descriptionTeaser") or ""),
                        "url": url, "id": "afl-" + str(jid), "source": "afl"})
        start += len(jobs)
        time.sleep(0.5)
    return out


# ---------------------------------------------------------------------------
# Oracle (Oracle Cloud HCM, API pública del sitio de empleos)
# ---------------------------------------------------------------------------
ORACLE_API = "https://eeho.fa.us2.oraclecloud.com/hcmRestApi/resources/latest/"
ORACLE_SITE = "CX_45001"
ORACLE_US = "300000000149325"
ORACLE_PAY = re.compile(r"from \$([\d,.]+) to \$([\d,.]+) per (hour|annum|year)", re.I)


def fetch_oracle_hcm(company: str, api: str, site: str, keywords: tuple, keep: "re.Pattern", job_url: str,
                     location_id: str | None = None, source: str = "oracle") -> list[dict]:
    """Sitios de empleo en Oracle Cloud HCM (Oracle, Black Box). Pide la lista por palabra clave y el detalle por puesto."""
    seen, out = set(), []
    for kw in keywords:
        offset = 0
        while True:
            loc = f",locationId={location_id}" if location_id else ""
            url = (f"{api}recruitingCEJobRequisitions?onlyData=true&expand=requisitionList.secondaryLocations"
                   f"&finder=findReqs;siteNumber={site},keyword=%22{urllib.parse.quote(kw)}%22{loc},limit=200,offset={offset},"
                   f"sortBy=POSTING_DATES_DESC")
            items = get(url).get("items") or [{}]
            rows = items[0].get("requisitionList") or []
            for r in rows:
                title = (r.get("Title") or "").strip()
                if r["Id"] in seen or not is_tech_title(title) or not keep.search(title):
                    continue
                seen.add(r["Id"])
                place = r.get("PrimaryLocation") or ""
                if place.strip() == "United States":  # sin ciudad: usar la primera ubicación secundaria de EE.UU.
                    for s2 in r.get("secondaryLocations") or []:
                        if (s2.get("CountryCode") == "US" or "United States" in (s2.get("Name") or "")) and "," in (s2.get("Name") or ""):
                            place = s2["Name"]
                            break
                if "United States" not in place and not re.search(r", [A-Z]{2}$", place):
                    continue
                place = place.replace(", United States", "")
                city, _, st = place.rpartition(", ")
                if city.isupper():
                    city = city.title()
                out.append({"company": company, "title": title, "loc": f"{city}, {st}" if city else place,
                            "posted": (r.get("PostedDate") or "")[:10], "pay": None,
                            "url": job_url.format(id=r["Id"]), "id": f"{source}-{r['Id']}", "source": source})
            if len(rows) < 200:
                break
            offset += 200

    def add_pay(r):
        try:
            d = get(f"{api}recruitingCEJobRequisitionDetails?expand=all&onlyData=true&finder=ById;"
                    f"Id=%22{r['id'].split('-', 1)[1]}%22,siteNumber={site}")
            text = strip_html(" ".join(str(v) for v in (d.get("items") or [{}])[0].values() if isinstance(v, str)))
            m = ORACLE_PAY.search(text)
            if m:
                r["pay"] = [m.group(1), m.group(2), "hour" if m.group(3).lower() == "hour" else "year"]
            else:
                r["pay"] = text[-3000:]  # parse_pay busca "$X - $Y" en el texto
        except Exception:
            pass
        return r

    with ThreadPoolExecutor(max_workers=3) as ex:
        return list(ex.map(add_pay, out))


def fetch_oracle() -> list[dict]:
    keep = re.compile(r"data ?cent|\bISP\b|\bDC\b|facilit", re.I)
    return fetch_oracle_hcm("Oracle", ORACLE_API, ORACLE_SITE, ("technician", "data center facilities", "critical facilities"),
                            keep, "https://careers.oracle.com/jobs/#en/sites/jobsearch/job/{id}", ORACLE_US, "oracle")


def fetch_blackbox() -> list[dict]:
    """Black Box: contratista de cableado y despliegue para hyperscalers."""
    keep = re.compile(r"network tech|infrastructure tech|cabl|fiber|low voltage|data ?cent|structured", re.I)
    return fetch_oracle_hcm("Black Box", "https://eoje.fa.us2.oraclecloud.com/hcmRestApi/resources/latest/", "CX_1001",
                            ("technician",), keep,
                            "https://eoje.fa.us2.oraclecloud.com/hcmUI/CandidateExperience/en/sites/CX_1001/job/{id}",
                            None, "blackbox")


# ---------------------------------------------------------------------------
# Vision Technologies (tablero Loxo, lista en el HTML)
# ---------------------------------------------------------------------------
VISION_URL = "https://vision-technologies.app.loxo.co/vision-technologies"
VISION_CARD = re.compile(r"""class=['"]job-title['"][^>]*href=['"]([^'"]+)['"][^>]*>\s*(.*?)\s*</a>.*?location_on</i>\s*(.*?)\s*</div>""", re.S)


def parse_vision(html_text: str) -> list[dict]:
    out = []
    for href, title, loc in VISION_CARD.findall(html_text):
        title = html.unescape(re.sub(r"<[^>]+>", "", title)).strip()
        if not is_tech_title(title) or not DC_TITLE.search(title) and not re.search(r"structured cabl", title, re.I):
            continue
        loc = html.unescape(loc).replace(", United States", "").strip()
        url = href if href.startswith("http") else "https://vision-technologies.app.loxo.co" + href
        out.append({"company": "Vision Technologies", "title": title, "loc": loc, "posted": "", "pay": None,
                    "url": url, "id": "vision-" + url.rsplit("/", 1)[-1][:40], "source": "vision"})
    return out


def fetch_vision() -> list[dict]:
    return parse_vision(get(VISION_URL, as_json=False))


# ---------------------------------------------------------------------------
# M.C. Dean (iCIMS): eléctrico, cableado y operación de instalaciones críticas
# ---------------------------------------------------------------------------
MCDEAN_KEEP = re.compile(r"critical facilit|\bUPS\b|medium voltage|communications technician|electrician|cabl|generator|data ?cent.*technician", re.I)
MCDEAN_PAY = re.compile(r"USD\s*\$([\d,.]+)\s*-\s*USD\s*\$([\d,.]+)\s*/\s*(Hr|Yr|Hour|Year)", re.I)


def fetch_mcdean() -> list[dict]:
    seen, out = set(), []
    for kw in ("critical facility technician", "data center", "UPS technician", "medium voltage", "electrician", "communications technician"):
        for page in range(1, 8):
            data = get(f"https://careers.mcdean.com/api/jobs?keywords={urllib.parse.quote(kw)}&page={page}&limit=100")
            jobs = data.get("jobs") or []
            for x in jobs:
                d = x.get("data") or x
                rid = d.get("req_id") or d.get("slug")
                title = (d.get("title") or "").strip()
                if rid in seen or not is_tech_title(title) or not MCDEAN_KEEP.search(title):
                    continue
                if (d.get("country_code") or "US") not in ("US", "USA") or not d.get("state"):
                    continue
                seen.add(rid)
                m = MCDEAN_PAY.search(strip_html(d.get("description") or ""))
                pay = [m.group(1), m.group(2), "hour" if m.group(3).lower().startswith("h") else "year"] if m else None
                out.append({"company": "M.C. Dean", "title": re.sub(r"\s*-\s*[A-Z][\w .]+,\s*[A-Z]{2}$", "", title),
                            "loc": f"{(d.get('city') or '').title()}, {d.get('state')}", "posted": (d.get("posted_date") or "")[:10],
                            "pay": pay, "url": f"https://careers.mcdean.com/jobs/{d.get('slug')}", "id": f"mcdean-{rid}", "source": "mcdean",
                            "desc": strip_html(d.get("description") or "")[:6000]})
            if len(jobs) < 100:
                break
            time.sleep(0.3)
    return out

# ---------------------------------------------------------------------------
# E2 Optics (iCIMS clásico): contratista de cableado ISP para hyperscale
# ---------------------------------------------------------------------------
E2_ROW = re.compile(r'Location</span>\s*<span\s*>\s*US-([A-Z]{2})-([^<]+?)\s*</span>.*?<a href="([^"]+)"[^>]*class="iCIMS_Anchor"[^>]*>.*?<h3\s*>\s*(.*?)\s*</h3>', re.S)
E2_KEEP = re.compile(r"technician|installer|network specialist|lead tech|splicer|low voltage|cabl", re.I)


def parse_e2(html_text: str) -> list[dict]:
    out = []
    for st, city, href, title in E2_ROW.findall(html_text):
        title = html.unescape(title).strip()
        if not E2_KEEP.search(title) or not is_tech_title(title) and not re.search(r"installer|network specialist|splicer", title, re.I):
            continue
        city = html.unescape(city).split(" - ")[0].strip()  # "Salt Lake City - Eagle Mountain" -> ciudad principal
        jid = (re.search(r"/jobs/(\d+)/", href) or [None, href])[1]
        out.append({"company": "E2 Optics", "title": title, "loc": f"{city}, {st}", "posted": "", "pay": None,
                    "url": href.split("?")[0], "id": f"e2-{jid}", "source": "e2optics"})
    return out


def fetch_e2() -> list[dict]:
    out, seen = [], set()
    for pr in range(0, 10):
        rows = parse_e2(get(f"https://careers-e2optics.icims.com/jobs/search?ss=1&searchRelation=keyword_all&pr={pr}&in_iframe=1", as_json=False))
        new = [r for r in rows if r["id"] not in seen]
        if not new:
            break
        seen.update(r["id"] for r in new)
        out += new
        time.sleep(0.3)
    return out


# ---------------------------------------------------------------------------
# UKG / UltiPro (ADB Companies): tablero con API JSON
# ---------------------------------------------------------------------------
ULTIPRO_SITES = [("ADB Companies", "https://recruiting2.ultipro.com/ADB1000ADBC/JobBoard/41648143-db27-4906-836e-7f9a417d1a19",
                  re.compile(r"data center|\bISP\b|structure cabl|structured cabl", re.I))]


def fetch_ultipro(company: str, board: str, keep: "re.Pattern") -> list[dict]:
    payload = {"opportunitySearch": {"Top": 500, "Skip": 0, "QueryString": "",
                                     "OrderBy": [{"Value": "postedDateDesc", "PropertyName": "PostedDate", "Ascending": False}], "Filters": []},
               "matchCriteria": {"PreferredJobs": [], "Educations": [], "LicenseAndCertifications": [], "Skills": [],
                                 "hasNoLicenses": False, "SkillAssessments": []}}
    data = post_json(board + "/JobBoardView/LoadSearchResults", payload)
    out = []
    for o in data.get("opportunities") or []:
        title = re.sub(r"^\W+|\W+$", "", (o.get("Title") or "").strip())
        if not keep.search(title) or not is_tech_title(title):
            continue
        locs = [l.get("LocalizedName") or "" for l in (o.get("Locations") or [])]
        locs = [re.sub(r"^Data Center - ", "", x).strip() for x in locs if x and x.strip() not in ("Remote", "")]
        # ADB usa nombres sueltos ("Abilene", "New Albany", "TEXAS"); se completan con ciudades conocidas
        known = {"Abilene": "Abilene, TX", "New Albany": "New Albany, OH", "Columbus": "Columbus, OH", "Chicago": "Chicago, IL",
                 "Pittsburgh": "Pittsburgh, PA", "Denver": "Denver, CO", "Atlanta": "Atlanta, GA"}
        loc = ""
        for x in locs:
            if "," in x:
                loc = x; break
            if x.title() in known:
                loc = known[x.title()]; break
        if not loc:
            for x in locs:
                if x.upper() in STATE_BY_NAME_UPPER:
                    loc = STATE_BY_NAME_UPPER[x.upper()]; break
        if not loc:
            continue
        out.append({"company": company, "title": title, "loc": loc, "posted": (o.get("PostedDate") or "")[:10], "pay": None,
                    "url": f"{board}/OpportunityDetail?opportunityId={o.get('Id')}", "id": f"ultipro-{o.get('Id')}", "source": "ultipro"})
    return out


STATE_BY_NAME_UPPER = {v.upper(): k for k, v in US_STATES.items()}


# ---------------------------------------------------------------------------
# Team LINX (teamlinx.com): contratista de bajo voltaje / cableado ISP para data centers
# (Oracle Abilene, entre otros). Tabla HTML "Job Position | Location" + página por puesto con "Pay:".
# ---------------------------------------------------------------------------
LINX_ROW = re.compile(r'<tr[^>]*>\s*<td[^>]*>\s*<a href="(https://teamlinx\.com/career/[^"]+)"[^>]*>\s*(.*?)\s*</a>\s*</td>\s*<td[^>]*>\s*(.*?)\s*</td>'
                      r'(?:\s*<!--td>(\d\d-\d\d-\d{4})</td-->)?', re.S)
LINX_KEEP = re.compile(r"technician|foreman|splic|installer|lead tech", re.I)
LINX_PAY = re.compile(r"Pay(?: Rate)?(?:</strong>)?:\s*(?:</strong>\s*)?(.{0,200}?)(?:&nbsp;|</p|<br)", re.S)
LINX_AMOUNT = re.compile(r"\$\s?(\d{1,3}(?:\.\d\d)?)\b")


def parse_linx_table(html_text: str) -> list[dict]:
    out = []
    for href, title, locs, d in LINX_ROW.findall(html_text):
        title = html.unescape(re.sub(r"<[^>]+>", "", title)).replace("–", "-").strip()
        locs = html.unescape(re.sub(r"<[^>]+>", "", locs)).strip()
        if not LINX_KEEP.search(title) or re.search(r"quality|training|superintend|manager|estimator|commercial construction", title, re.I):
            continue
        if not (DC_TITLE.search(title) or re.search(r"splic|fiber", title, re.I)):
            continue  # solo data center / fibra; lo comercial no va en el sitio
        posted = f"{d[6:10]}-{d[0:2]}-{d[3:5]}" if d else ""  # la fecha viene en un comentario HTML (MM-DD-YYYY)
        out.append({"title": title, "href": href, "locs": locs, "posted": posted})
    return out


def parse_linx_job(html_text: str) -> tuple:
    """Devuelve (pay, posted, desc): pay = (min, max, 'hour') o None."""
    pay = None
    m = LINX_PAY.search(html_text)
    if m:
        nums = [float(x) for x in LINX_AMOUNT.findall(html.unescape(m.group(1)))]
        if nums and min(nums) >= 10:
            pay = (min(nums), max(nums), "hour")
    d = re.search(r'datePublished"\s*:\s*"(\d{4}-\d\d-\d\d)', html_text)
    body = re.search(r"<article[\s\S]*?</article>|<main[\s\S]*?</main>", html_text)
    return pay, (d.group(1) if d else ""), strip_html(re.sub(r"<script[\s\S]*?</script>", "", (body.group(0) if body else html_text)))[:6000]


def linx_locations(locs: str) -> list[str]:
    out = []
    for part in re.split(r"\s*[|,]\s*(?=[A-Z][a-z]|Travel)", locs):
        part = part.strip().rstrip(",")
        if not part:
            continue
        if part.lower() == "travel":
            out.append("Travel - US")
            continue
        m = re.match(r"^(.*?),?\s+([A-Z]{2})$", part)
        if m:
            out.append(f"{m.group(1).strip()}, {m.group(2)}")
    return out


def fetch_linx() -> list[dict]:
    out = []
    for r in parse_linx_table(get("https://teamlinx.com/careers/", as_json=False)):
        try:
            pay, posted, desc = parse_linx_job(get(r["href"], as_json=False))
        except Exception as e:
            print("aviso: linx", r["href"], e, file=sys.stderr)
            pay, posted, desc = None, "", ""
        posted = posted or r["posted"]
        slug = r["href"].rstrip("/").rsplit("/", 1)[-1]
        for loc in linx_locations(r["locs"]):
            out.append({"company": "Team LINX", "title": r["title"], "loc": loc, "posted": posted, "pay": pay, "desc": desc,
                        "url": r["href"], "id": f"linx-{slug}-{re.sub(r'[^a-z]', '', loc.lower())}", "source": "linx"})
        time.sleep(0.3)
    return out


# ---------------------------------------------------------------------------
# JazzHR (applytojob.com): The Archetype Strategy, proveedor de mano de obra para data centers (Tye, TX / Abilene)
# ---------------------------------------------------------------------------
JAZZ_ROW = re.compile(r'<li class="list-group-item">\s*<h3[^>]*>\s*<a href="([^"]+)">\s*(.*?)\s*</a>\s*</h3>\s*<ul[^>]*>\s*<li>(?:<i[^>]*></i>)?\s*(.*?)\s*</li>', re.S)
JAZZ_SITES = [("The Archetype Strategy", "https://archetypestrategy.applytojob.com/apply",
               re.compile(r"data center|fiber|splic|cable (puller|technician)|cabling", re.I))]
JAZZ_PAY = re.compile(r"(?:Pay|Compensation|Rate|Salary)[^$]{0,40}(\$\s?\d[\d,.]*\s*(?:-|–|to)\s*\$?\s?\d[\d,.]*\s*(?:per hour|/\s?hour|/hr|an hour|hourly|per year|/yr|annually)?)", re.I)
TYPO_CITIES = {"Abeline": "Abilene", "Road Oak": "Red Oak", "Loudon": "Loudoun", "Louden": "Loudoun", "Spartansburg": "Spartanburg"}


def parse_jazz_list(html_text: str, company: str, keep: "re.Pattern") -> list[dict]:
    out = []
    for href, title, loc in JAZZ_ROW.findall(html_text):
        title = html.unescape(re.sub(r"<[^>]+>", "", title)).replace("–", "-").strip()
        loc = html.unescape(re.sub(r"<[^>]+>", "", loc)).strip()
        if not keep.search(title) or not is_tech_title(title):
            continue
        if re.search(r"cleaning|security|access control|cctv|electrician|project manager", title, re.I):
            continue
        city, st = (loc.rsplit(",", 1) + [""])[:2] if "," in loc else ("", loc)
        city, st = TYPO_CITIES.get(city.strip(), city.strip()), st.strip()
        if st not in US_STATES:
            continue  # "TX", "United States", "(Multiple states)": sin ciudad no se publica
        jid = href.rstrip("/").split("/apply/")[-1].split("/")[0]
        out.append({"company": company, "title": title, "loc": f"{city}, {st}" if city else US_STATES[st], "posted": "",
                    "pay": None, "url": href, "id": f"jazz-{jid}", "source": "jazzhr"})
    return out


def parse_jazz_job(html_text: str):
    text = html.unescape(re.sub(r"<[^>]+>", " ", re.sub(r"<script[\s\S]*?</script>", "", html_text)))
    m = JAZZ_PAY.search(text)
    if not m:
        return None
    lo, hi, unit = parse_pay(m.group(1))
    return (lo, hi, unit) if lo else None


def jazz_desc(html_text: str) -> str:
    body = re.search(r'id="job-description"[\s\S]*?(?=<form|<div class="apply|$)', html_text)
    return strip_html(re.sub(r"<script[\s\S]*?</script>", "", body.group(0) if body else html_text))[:6000]


def fetch_jazz(company: str, board: str, keep: "re.Pattern") -> list[dict]:
    rows = parse_jazz_list(get(board, as_json=False), company, keep)
    for r in rows:
        try:
            page = get(r["url"], as_json=False)
            r["pay"] = parse_jazz_job(page)
            r["desc"] = jazz_desc(page)
        except Exception as e:
            print("aviso: jazz", r["url"], e, file=sys.stderr)
        time.sleep(0.2)
    return rows


# ---------------------------------------------------------------------------
# CareerPlug (Telvero): lista HTML + página por puesto con "Pay:" y per diem
# ---------------------------------------------------------------------------
CAREERPLUG_SITES = [("Telvero", "https://telvero.careerplug.com")]
CP_ROW = re.compile(r'<a[^>]+href="(/jobs/(\d+))"[^>]*>.*?<span class="name">(.*?)</span>.*?Location:</span>\s*([^<]+?)\s*</div>', re.S)
CP_PAY = re.compile(r"Pay(?: Rate)?:\s*(\$\s?\d[\d,.]*\s*(?:to|-|–)\s*\$?\s?\d[\d,.]*\s*(?:per hour|/\s?hour|/hr|an hour|hourly)?)", re.I)


def parse_careerplug(html_text: str, company: str, base: str) -> list[dict]:
    out = []
    for href, jid, title, loc in CP_ROW.findall(html_text):
        title = html.unescape(re.sub(r"<[^>]+>", "", title)).strip()
        if not is_tech_title(title) and not re.search(r"splic|installer", title, re.I):
            continue
        m = re.match(r"([A-Z]{2})-([^-]+?)\s*-\s*\d{5}", html.unescape(loc).strip())  # "TX-Abilene-79601"
        if not m:
            continue
        out.append({"company": company, "title": title, "loc": f"{m.group(2).strip()}, {m.group(1)}", "posted": "", "pay": None,
                    "url": base + href, "id": f"careerplug-{jid}", "source": "careerplug"})
    return out


def fetch_careerplug(company: str, base: str) -> list[dict]:
    rows = parse_careerplug(get(base + "/jobs", as_json=False), company, base)
    for r in rows:
        try:
            page = get(r["url"], as_json=False)
            text = strip_html(re.sub(r"<script[\s\S]*?</script>", "", page))
            m = CP_PAY.search(text)
            if m:
                lo, hi, unit = parse_pay(m.group(1))
                if lo:
                    r["pay"] = (lo, hi, unit)
            d = re.search(r'datePosted"\s*:\s*"(\d{4}-\d\d-\d\d)', page)
            r["posted"] = d.group(1) if d else ""
            r["desc"] = text[:6000]
        except Exception as e:
            print("aviso: careerplug", r["url"], e, file=sys.stderr)
        time.sleep(0.3)
    return rows


# ---------------------------------------------------------------------------
# ApplicantPro (SRI Telecom): API JSON /core/jobs/{siteId}?getParams={}
# ---------------------------------------------------------------------------
APPLICANTPRO_SITES = [("SRI Telecom", "sritelecom", 10497, re.compile(r"data center|\bISP\b|fiber|splic|cabl", re.I))]


def fetch_applicantpro(company: str, sub: str, site_id: int, keep: "re.Pattern") -> list[dict]:
    data = get(f"https://{sub}.applicantpro.com/core/jobs/{site_id}?getParams=%7B%7D")
    out = []
    for j in (data.get("data") or {}).get("jobs") or []:
        title = html.unescape(j.get("title") or "").strip()
        if not keep.search(title) or not is_tech_title(title):
            continue
        city, st = (j.get("city") or "").strip(), (j.get("abbreviation") or "").strip()
        if not st:
            continue
        pay = None
        if j.get("minSalary") and j.get("maxSalary"):
            pay = (float(j["minSalary"]), float(j["maxSalary"]), "hour" if (j.get("payType") or "").lower().startswith("hour") else "year")
        url = j.get("jobUrl") or f"https://{sub}.applicantpro.com/jobs/{j.get('id')}"
        row = {"company": company, "title": title, "loc": f"{city}, {st}" if city else STATE_BY_NAME_UPPER.get(st.upper(), st),
               "posted": parse_date(j.get("startDateRef") or ""), "pay": pay, "url": url, "id": f"applicantpro-{j.get('id')}", "source": "applicantpro"}
        try:
            row["desc"] = strip_html(re.sub(r"<script[\s\S]*?</script>", "", get(url, as_json=False)))[:6000]
        except Exception as e:
            print("aviso: applicantpro", url, e, file=sys.stderr)
        time.sleep(0.3)
        out.append(row)
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
    for fn in (fetch_microsoft, fetch_google, fetch_introl, fetch_afl, fetch_oracle, fetch_rosendin,
               fetch_blackbox, fetch_vision, fetch_mcdean, fetch_e2, fetch_linx):
        try:
            raw["other"] += fn()
        except Exception as e:  # una fuente caída no debe tumbar todo
            print("aviso:", fn.__name__, e, file=sys.stderr)
    for company, board, keep in ULTIPRO_SITES:
        try:
            raw["other"] += fetch_ultipro(company, board, keep)
        except Exception as e:
            print("aviso: ultipro", company, e, file=sys.stderr)
    for company, base in CAREERPLUG_SITES:
        try:
            raw["other"] += fetch_careerplug(company, base)
        except Exception as e:
            print("aviso: careerplug", company, e, file=sys.stderr)
    for company, sub, site_id, keep in APPLICANTPRO_SITES:
        try:
            raw["other"] += fetch_applicantpro(company, sub, site_id, keep)
        except Exception as e:
            print("aviso: applicantpro", company, e, file=sys.stderr)
    for company, board, keep in JAZZ_SITES:
        try:
            raw["other"] += fetch_jazz(company, board, keep)
        except Exception as e:
            print("aviso: jazzhr", company, e, file=sys.stderr)
    for org, company in LEVER_ORGS.items():
        try:
            raw["other"] += fetch_lever(org, company)
        except Exception as e:
            print("aviso: lever", org, e, file=sys.stderr)
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
            "hourly_min", "hourly_max", "pay_min", "pay_max", "pay_unit", "perks", "per_diem", "entry", "url", "source", "job_id"]
    with open(outdir / "jobs.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=cols, extrasaction="ignore")
        w.writeheader()
        for j in jobs:
            w.writerow(asdict(j))
    with open(outdir / "jobs.json", "w", encoding="utf-8") as f:
        json.dump([{k: v for k, v in asdict(j).items() if k not in ("pay_text", "desc")} for j in jobs], f,
                  ensure_ascii=False, indent=1)


MAX_KEEP_DAYS = 5


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
    for j in jobs:
        j.last_seen = today.isoformat()
    names = set(Job.__dataclass_fields__)
    kept, expired = [], 0
    for d in prev:
        if d.get("company") in live:
            continue
        j = Job(**{k: v for k, v in d.items() if k in names})
        seen = date.fromisoformat(j.last_seen) if j.last_seen else today
        if (today - seen).days > MAX_KEEP_DAYS:  # la fuente lleva días sin responder: la vacante ya no es confiable
            expired += 1
            continue
        if j.posted:
            j.days_posted = (today - date.fromisoformat(j.posted)).days
        kept.append(j)
    if expired:
        print(f"aviso: {expired} vacantes conservadas caducaron (fuente sin responder más de {MAX_KEEP_DAYS} días)", file=sys.stderr)
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
