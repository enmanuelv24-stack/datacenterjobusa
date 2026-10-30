"""Une los datos guardados de hoy (recolectados con el navegador) en un solo raw.json
con el formato que entiende collector.py."""
import json
import sys
from pathlib import Path

d = Path(sys.argv[1] if len(sys.argv) > 1 else "data")
raw = json.loads((d / "raw_greenhouse_ashby_2026-10-30.json").read_text())
amazon = []
for line in (d / "raw_amazon_groups_2026-10-30.txt").read_text().splitlines():
    if not line.strip() or line.startswith("#"):
        continue
    t, loc, n, newest, oldest, lo, hi, unit, jid = line.split("|")
    amazon.append({"id": jid, "path": f"/en/jobs/{jid}", "t": t, "loc": loc, "n": int(n),
                   # fecha de la publicación más reciente con ese puesto y ubicación
                   "d": newest, "pay": [lo, hi, unit] if lo else None})
raw["amazon"] = amazon

URL_PREFIX = {"MS:": "https://apply.careers.microsoft.com/careers/job/",
              "G:": "https://www.google.com/about/careers/applications/jobs/results/"}
other = []
for path in sorted(d.glob("raw_other_*.txt")):
    for line in path.read_text().splitlines():
        if not line.strip() or line.startswith("#"):
            continue
        parts = line.split("|")
        if len(parts) == 6:   # empresa|titulo|ubicacion|publicada|texto_pago|url  (Workday)
            company, title, loc, posted, pay_text, url = parts
            pay = pay_text
        else:                 # empresa|titulo|ubicacion|publicada|min|max|unidad|url
            company, title, loc, posted, lo, hi, unit, url = parts
            pay = [lo, hi, unit] if lo else None
        for k, v in URL_PREFIX.items():
            if url.startswith(k):
                url = v + url[len(k):]
        other.append({"company": company, "title": title, "loc": loc, "posted": posted, "pay": pay,
                      "url": url, "id": url, "source": "careers"})
raw["other"] = other
print(len(other), "vacantes de otras empresas")
(d / "raw_2026-10-30.json").write_text(json.dumps(raw, ensure_ascii=False))
print(len(amazon), "grupos de Amazon;", sum(a["n"] for a in amazon), "vacantes")
