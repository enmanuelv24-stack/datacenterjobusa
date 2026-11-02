"""
Agrega las respuestas de la encuesta (CSV exportado de la hoja "DCJ Survey Responses") en data/survey.json.
Solo se publican agregados por empresa con 3 o más respuestas; nunca filas individuales ni texto libre.

    python survey_aggregate.py responses.csv --out data/survey.json
"""
from __future__ import annotations

import argparse
import csv
import json
import re
import statistics
from collections import defaultdict
from pathlib import Path

MIN_RESPONSES = 3

# Normalización de nombres de empresa escritos a mano -> nombre que usa el sitio
ALIASES = {
    "nti": "Network Connex", "national technologies": "Network Connex", "network connex": "Network Connex", "nti connect": "Network Connex",
    "afl": "AFL", "linx": "Team LINX", "team linx": "Team LINX", "e2": "E2 Optics", "e2 optics": "E2 Optics", "adb": "ADB Companies",
    "amazon": "Amazon", "aws": "Amazon", "google": "Google", "microsoft": "Microsoft", "oracle": "Oracle", "qts": "QTS", "equinix": "Equinix",
    "black box": "Black Box", "introl": "Introl", "tds": "TDS (Total Deployment Solutions)", "total deployment": "TDS (Total Deployment Solutions)",
    "mc dean": "M.C. Dean", "m.c. dean": "M.C. Dean", "archetype": "The Archetype Strategy", "ais": "The Archetype Strategy",
    "telvero": "Telvero", "sri": "SRI Telecom", "sri telecom": "SRI Telecom", "align": "Align", "midpoint": "MidPoint Technology Group",
    "coreweave": "CoreWeave", "xai": "xAI", "rosendin": "Rosendin", "holder": "Holder Construction", "vision": "Vision Technologies",
}


def norm_company(s: str) -> str:
    k = re.sub(r"[^a-z0-9. ]+", " ", (s or "").lower()).strip()
    k = re.sub(r"\s+", " ", k)
    for alias, name in ALIASES.items():
        if k == alias or k.startswith(alias + " ") or (" " + alias) in (" " + k):
            return name
    return (s or "").strip()


def col(row: dict, *keys: str) -> str:
    for h, v in row.items():
        hl = (h or "").lower()
        if all(k in hl for k in keys):
            return (v or "").strip()
    return ""


def num(s: str):
    m = re.search(r"\d+(?:\.\d+)?", (s or "").replace(",", ""))
    return float(m.group(0)) if m else None


def mode(values):
    values = [v for v in values if v]
    if not values:
        return ""
    return max(set(values), key=values.count)


def aggregate(rows: list[dict]) -> dict:
    by = defaultdict(list)
    for r in rows:
        c = norm_company(col(r, "who do you work for"))
        if c:
            by[c].append(r)
    out = {}
    for c, rs in by.items():
        if len(rs) < MIN_RESPONSES:
            continue
        pays = [p for p in (num(col(r, "base hourly pay")) for r in rs) if p and 10 <= p <= 250]
        hours = [h for h in (num(col(r, "hours you actually work")) for r in rs) if h and 20 <= h <= 100]
        out[c] = {
            "n": len(rs),
            "pay_median": round(statistics.median(pays), 2) if pays else None,
            "hours_week_median": round(statistics.median(hours)) if hours else None,
            "shift": mode([col(r, "shift pattern") for r in rs]),
            "per_diem": mode([col(r, "per diem") for r in rs]),
            "housing": mode([col(r, "housing") for r in rs]),
            "rotation": mode([col(r, "rotation") for r in rs]),
            "overtime": mode([col(r, "overtime at your site") for r in rs]),
            "night_diff": mode([col(r, "night shift differential") for r in rs]),
            "again_yes_pct": round(100 * sum(1 for r in rs if col(r, "work for that employer again").lower().startswith("yes")) / len(rs)),
            "states": sorted({col(r, "state where you work").upper()[:2] for r in rs if col(r, "state where you work")}),
        }
    return {"min_responses": MIN_RESPONSES, "total_responses": len(rows), "companies": out}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("csv")
    ap.add_argument("--out", default="data/survey.json")
    a = ap.parse_args()
    with open(a.csv, newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    data = aggregate(rows)
    Path(a.out).parent.mkdir(parents=True, exist_ok=True)
    Path(a.out).write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"{data['total_responses']} respuestas -> {len(data['companies'])} empresas con {MIN_RESPONSES}+ -> {a.out}")


if __name__ == "__main__":
    main()
