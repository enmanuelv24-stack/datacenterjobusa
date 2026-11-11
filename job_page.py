"""Piezas de la ficha de cada vacante: la paga como protagonista, la fecha legible y la descripción en bloques."""
import html
from datetime import date

E = html.escape

BULLET_MAX_CHARS = 200   # una línea más corta que esto, junto a otra igual, se muestra como viñeta
MIN_BULLET_RUN = 2       # cuántas líneas cortas seguidas hacen falta para armar una lista


def _dollars(v: float, cents: bool) -> str:
    return f"${v:,.2f}" if cents else f"${v:,.0f}"


def pay_hero(job: dict) -> str:
    """La paga en grande, igual que en la tarjeta de la lista: por hora primero y el anual debajo si el empleador lo publicó así."""
    lo, hi = job.get("hourly_min"), job.get("hourly_max")
    if not lo:
        return '<p class="payhero nopay"><b>Pay not posted</b><small>Ask the recruiter before you apply</small></p>'
    yearly = ""
    if job.get("pay_unit") == "year" and job.get("pay_min"):
        yearly = f' · {_dollars(job["pay_min"], False)}–{_dollars(job["pay_max"], False)} per year'
    return (f'<p class="payhero"><b>{_dollars(lo, True)}–{_dollars(hi, True)}</b>'
            f'<small>per hour{yearly} · posted by the employer</small></p>')


def posted_label(iso: str | None) -> str:
    """'2026-11-04' -> 'Nov 4, 2026'. Sin fecha o con una fecha ilegible devuelve una raya."""
    if not iso:
        return "—"
    try:
        d = date.fromisoformat(iso)
    except ValueError:
        return "—"
    return f"{d:%b} {d.day}, {d.year}"


def description_html(text: str) -> str:
    """Convierte la descripción (una idea por línea) en párrafos, y las líneas cortas seguidas en una lista con viñetas."""
    lines = [ln.strip() for ln in (text or "").splitlines() if ln.strip()]
    blocks: list[str] = []
    run: list[str] = []

    def flush() -> None:
        if len(run) >= MIN_BULLET_RUN:
            blocks.append("<ul>" + "".join(f"<li>{E(x)}</li>" for x in run) + "</ul>")
        else:
            blocks.extend(f"<p>{E(x)}</p>" for x in run)
        run.clear()

    for ln in lines:
        if len(ln) <= BULLET_MAX_CHARS:
            run.append(ln)
            continue
        flush()
        blocks.append(f"<p>{E(ln)}</p>")
    flush()
    return "".join(blocks)
