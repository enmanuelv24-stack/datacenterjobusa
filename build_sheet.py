"""Arma la hoja de revisión (Excel) a partir de data/jobs.json."""
import json
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

from openpyxl import Workbook
from openpyxl.comments import Comment
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter
from openpyxl.worksheet.datavalidation import DataValidation

SRC = Path(sys.argv[1] if len(sys.argv) > 1 else "data/jobs.json")
OUT = Path(sys.argv[2] if len(sys.argv) > 2 else "vacantes_data_center_2026-10-30.xlsx")
jobs = json.loads(SRC.read_text())

F = "Arial"
H = Font(name=F, bold=True, color="FFFFFF")
HF = PatternFill("solid", fgColor="1F3A5F")
B = Font(name=F)
BB = Font(name=F, bold=True)
TITLE = Font(name=F, bold=True, size=14)
INPUT = PatternFill("solid", fgColor="FFFF00")
THIN = Border(bottom=Side(style="thin", color="D0D0D0"))
MONEY = '"$"#,##0.00;-"$"#,##0.00;"-"'


def header(ws, row, cols, widths):
    for i, (c, w) in enumerate(zip(cols, widths), 1):
        cell = ws.cell(row=row, column=i, value=c)
        cell.font, cell.fill = H, HF
        cell.alignment = Alignment(wrap_text=True, vertical="center")
        ws.column_dimensions[get_column_letter(i)].width = w
    ws.row_dimensions[row].height = 32


def base_title(t: str) -> str:
    t = re.sub(r"\s+-\s+.*$", "", t)            # "Data Center Technician - Afton, TX"
    t = t.split(",")[0]                          # quita el equipo de Amazon
    t = re.sub(r"\(.*?\)", "", t)
    t = re.sub(r"\b(night (shift|role)|nights?|swing shift|maf hiring event|internship)\b", "", t, flags=re.I)
    t = re.sub(r"\s{2,}", " ", t).strip(" -,")
    return t


wb = Workbook()

# ---------------------------------------------------------------- Léeme
ws = wb.active
ws.title = "Léeme"
lines = [
    ("Vacantes de técnicos de data center: primera recolección", TITLE),
    ("Recolectado el 30 de octubre de 2026 desde las páginas de empleo oficiales de cada empresa.", B),
    ("", B),
    ("Fuentes", BB),
    ("Amazon: amazon.jobs (búsqueda pública y página de cada vacante, para el salario).", B),
    ("xAI y CoreWeave: API pública de Greenhouse (boards-api.greenhouse.io).", B),
    ("Crusoe y Lambda: API pública de Ashby (api.ashbyhq.com).", B),
    ("No se usó Indeed, LinkedIn ni otros agregadores.", B),
    ("", B),
    ("Cómo leer los datos", BB),
    ("Vacantes = cuántas publicaciones tiene la empresa con ese mismo puesto en esa ciudad (Amazon publica muchas iguales).", B),
    ("$/hora = rango publicado por la empresa. Si venía anual, se convirtió con 2,080 horas al año.", B),
    ("Días = días desde la publicación más reciente. Si sigue en la página de la empresa, sigue abierta.", B),
    ("Categoría y Nivel los propuso el programa a partir del título; pueden estar mal. Para eso es la pestaña de revisión.", B),
    ("Promedios del comparador: promedio simple de los rangos publicados por puesto y ubicación, sin ponderar por número de vacantes.", B),
    ("", B),
    ("Lo que necesito de ti (pestaña 'Títulos a revisar')", BB),
    ("Llena solo las celdas amarillas. Ejemplo de una fila llena:", B),
    ("Título: Engineering Operations Technician  |  ¿Es técnico?: Sí  |  Nivel real: II  |  "
     "Nombre común: EOT / técnico de instalaciones críticas  |  Notas: mismo trabajo que critical facilities tech", B),
    ("", B),
    ("Limitaciones", BB),
    ("Solo 5 empresas por ahora. Faltan Microsoft, Google, Meta, Equinix, Digital Realty y otras (usan otros sistemas).", B),
    ("xAI no publica salario en Tennessee ni Mississippi (esos estados no lo exigen).", B),
]
for i, (txt, font) in enumerate(lines, 1):
    c = ws.cell(row=i, column=1, value=txt)
    c.font = font
ws.column_dimensions["A"].width = 120

# ---------------------------------------------------------------- Vacantes
wv = wb.create_sheet("Vacantes")
cols = ["Empresa", "Puesto", "Categoría", "Nivel", "Ciudad", "Estado", "Vacantes",
        "Publicada", "Días", "$/hora mín", "$/hora máx", "Link"]
header(wv, 1, cols, [11, 52, 24, 7, 16, 7, 9, 11, 7, 11, 11, 14])
for r, j in enumerate(jobs, 2):
    vals = [j["company"], j["title"], j["role"], j["level"], j["city"], j["state"], j["openings"],
            j["posted"], j["days_posted"], j["hourly_min"], j["hourly_max"], "Abrir"]
    for c, v in enumerate(vals, 1):
        cell = wv.cell(row=r, column=c, value=v)
        cell.font = B
    wv.cell(row=r, column=12).hyperlink = j["url"]
    wv.cell(row=r, column=12).font = Font(name=F, color="0563C1", underline="single")
    for c in (10, 11):
        wv.cell(row=r, column=c).number_format = MONEY
n = len(jobs) + 1
wv.freeze_panes = "C2"
wv.auto_filter.ref = f"A1:L{n}"
RNG = lambda col: f"Vacantes!${col}$2:${col}${n}"  # noqa: E731

# ---------------------------------------------------------------- Resumen
wr = wb.create_sheet("Resumen")
wr["A1"], wr["A1"].font = "Resumen", TITLE
wr["A2"] = "Todas las cifras son fórmulas sobre la pestaña Vacantes."
wr["A2"].font = Font(name=F, italic=True, color="666666")

wr["A4"], wr["A4"].font = "Total de vacantes", BB
wr["B4"] = f"=SUM({RNG('G')})"
wr["A5"], wr["A5"].font = "Vacantes con salario publicado", BB
wr["B5"] = f'=SUMIFS({RNG("G")},{RNG("J")},">0")'
wr["A6"], wr["A6"].font = "% con salario", BB
wr["B6"] = "=IF(B4=0,0,B5/B4)"
wr["B6"].number_format = "0.0%"
for c in ("B4", "B5", "B6"):
    wr[c].font = B

row = 8
header(wr, row, ["Empresa", "Vacantes", "Con salario", "$/hora mín (prom.)", "$/hora máx (prom.)"], [30, 12, 12, 16, 16])
for comp, _ in Counter(j["company"] for j in jobs).most_common():
    row += 1
    wr.cell(row=row, column=1, value=comp)
    wr.cell(row=row, column=2, value=f'=SUMIFS({RNG("G")},{RNG("A")},A{row})')
    wr.cell(row=row, column=3, value=f'=SUMIFS({RNG("G")},{RNG("A")},A{row},{RNG("J")},">0")')
    wr.cell(row=row, column=4, value=f'=IFERROR(AVERAGEIFS({RNG("J")},{RNG("A")},A{row}),"-")')
    wr.cell(row=row, column=5, value=f'=IFERROR(AVERAGEIFS({RNG("K")},{RNG("A")},A{row}),"-")')
    for c in range(1, 6):
        wr.cell(row=row, column=c).font = B
    for c in (4, 5):
        wr.cell(row=row, column=c).number_format = MONEY

row += 2
header_row = row
for i, h in enumerate(["Estado", "Vacantes", "Con salario", "$/hora mín (prom.)", "$/hora máx (prom.)"], 1):
    cell = wr.cell(row=row, column=i, value=h)
    cell.font, cell.fill = H, HF
state_counts = defaultdict(int)
for j in jobs:
    state_counts[j["state"]] += j["openings"]
for st, _ in sorted(state_counts.items(), key=lambda x: -x[1]):
    row += 1
    wr.cell(row=row, column=1, value=st)
    wr.cell(row=row, column=2, value=f'=SUMIFS({RNG("G")},{RNG("F")},A{row})')
    wr.cell(row=row, column=3, value=f'=SUMIFS({RNG("G")},{RNG("F")},A{row},{RNG("J")},">0")')
    wr.cell(row=row, column=4, value=f'=IFERROR(AVERAGEIFS({RNG("J")},{RNG("F")},A{row}),"-")')
    wr.cell(row=row, column=5, value=f'=IFERROR(AVERAGEIFS({RNG("K")},{RNG("F")},A{row}),"-")')
    for c in range(1, 6):
        wr.cell(row=row, column=c).font = B
    for c in (4, 5):
        wr.cell(row=row, column=c).number_format = MONEY
wr.freeze_panes = "A9"

# ---------------------------------------------------------------- Comparador
wc = wb.create_sheet("Comparador")
wc["A1"], wc["A1"].font = "Comparador de salarios por categoría y empresa ($/hora, promedio de rangos publicados)", TITLE
roles = [r for r, _ in Counter(j["role"] for j in jobs).most_common()]
comps = [c for c, _ in Counter(j["company"] for j in jobs).most_common()]
header(wc, 3, ["Categoría"] + [f"{c} mín" for c in comps] + [f"{c} máx" for c in comps],
       [28] + [13] * (2 * len(comps)))
for i, role in enumerate(roles):
    r = 4 + i
    wc.cell(row=r, column=1, value=role).font = B
    for k, comp in enumerate(comps):
        for off, colL in ((0, "J"), (len(comps), "K")):
            col = 2 + k + off
            hdr = get_column_letter(col)
            comp_ref = f'"{comp}"'
            cell = wc.cell(row=r, column=col,
                           value=f'=IFERROR(AVERAGEIFS({RNG(colL)},{RNG("C")},$A{r},{RNG("A")},{comp_ref}),"-")')
            cell.font, cell.number_format = B, MONEY
wc.cell(row=5 + len(roles), column=1,
        value="'-' = esa empresa no tiene vacantes con salario en esa categoría.").font = Font(name=F, italic=True, color="666666")
wc.freeze_panes = "B4"

# ---------------------------------------------------------------- Títulos a revisar
wt = wb.create_sheet("Títulos a revisar")
wt["A1"], wt["A1"].font = "Títulos de puesto para que los clasifiques (llena solo lo amarillo)", TITLE
cols = ["Título (simplificado)", "Empresas", "Vacantes", "Categoría propuesta", "Nivel propuesto",
        "¿Es técnico? (Sí/No)", "Nivel real (I-IV)", "Nombre común en la industria", "Notas"]
header(wt, 3, cols, [48, 26, 10, 26, 10, 14, 12, 32, 40])
groups = defaultdict(lambda: {"companies": set(), "n": 0, "roles": Counter(), "levels": Counter()})
for j in jobs:
    g = groups[base_title(j["title"])]
    g["companies"].add(j["company"])
    g["n"] += j["openings"]
    g["roles"][j["role"]] += 1
    g["levels"][j["level"]] += 1
dv = DataValidation(type="list", formula1='"Sí,No"', allow_blank=True)
dv2 = DataValidation(type="list", formula1='"I,II,III,IV,No aplica"', allow_blank=True)
wt.add_data_validation(dv)
wt.add_data_validation(dv2)
r = 3
for t, g in sorted(groups.items(), key=lambda x: -x[1]["n"]):
    r += 1
    vals = [t, ", ".join(sorted(g["companies"])), g["n"], g["roles"].most_common(1)[0][0],
            g["levels"].most_common(1)[0][0]]
    for c, v in enumerate(vals, 1):
        wt.cell(row=r, column=c, value=v).font = B
    for c in range(6, 10):
        cell = wt.cell(row=r, column=c)
        cell.fill, cell.font = INPUT, B
    dv.add(f"F{r}")
    dv2.add(f"G{r}")
wt.freeze_panes = "B4"
wt["F3"].comment = Comment("¿Este puesto es de técnico de operación de data center? Sí / No", "Claude")

for sheet in wb.worksheets:
    sheet.sheet_view.showGridLines = sheet.title in ("Vacantes", "Títulos a revisar")

wb.save(OUT)
print("guardado", OUT, "títulos únicos:", len(groups))
