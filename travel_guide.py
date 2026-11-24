"""Sección "cuánto paga una semana de viaje" y preguntas frecuentes de travel-jobs.html.

Las cuentas salen de una vacante real del sitio (la de per diem y sueldo más bajos), así nunca exageran.
"""
from __future__ import annotations

import html

E = html.escape
OT_MULT = 1.5
STRAIGHT_HOURS = 40
HOURS = 72          # 6 turnos de 12 h
PD_DAYS = 7         # per diem de viajero: suele pagarse los 7 días; se dice en la página que hay que preguntarlo


def week_pay(rate: float, per_diem: float, hours: int = HOURS, pd_days: int = PD_DAYS) -> dict:
    straight = STRAIGHT_HOURS * rate
    overtime = (hours - STRAIGHT_HOURS) * rate * OT_MULT
    pd_week = per_diem * pd_days
    return {"straight": straight, "overtime": overtime, "per_diem": pd_week, "total": straight + overtime + pd_week}


def example_job(jobs: list[dict]) -> dict | None:
    """La vacante con per diem y sueldo publicados más bajos (redondeo hacia abajo)."""
    both = [j for j in jobs if j.get("per_diem") and j.get("hourly_min")]
    return min(both, key=lambda j: (j["per_diem"], j["hourly_min"]), default=None)


def _usd(x: float) -> str:
    return f"${x:,.0f}" if x == int(x) else f"${x:,.2f}"


def travel_math_html(jobs: list[dict], job_href) -> str:
    j = example_job(jobs)
    if not j:
        return ""
    rate, pd = j["hourly_min"], j["per_diem"]
    w = week_pay(rate, pd)
    ot = rate * OT_MULT
    rows = (f'<tr><td>First 40 hours × {_usd(rate)}</td><td class=num>{_usd(w["straight"])}</td></tr>'
            f'<tr><td>{HOURS - STRAIGHT_HOURS} overtime hours × {_usd(ot)}</td><td class=num>{_usd(w["overtime"])}</td></tr>'
            f'<tr><td>Per diem {_usd(pd)} × {PD_DAYS} days</td><td class=num>{_usd(w["per_diem"])}</td></tr>'
            f'<tr><td><b>One week</b></td><td class=num><b>{_usd(w["total"])}</b></td></tr>')
    return ('<h2>What a travel week pays: the math</h2>'
            f'<p>Real example from a posting on this site: <a href="{E(job_href(j))}">{E(j["title"])} at {E(j["company"])}</a>, '
            f'{_usd(rate)}/hr (the low end of its range) and {_usd(pd)}/day per diem, on a 6×12 schedule ({HOURS} hours a week).</p>'
            f'<div class="tablebox"><table><tbody>{rows}</tbody></table></div>'
            '<p class="note">Per diem is usually untaxed when you work away from your tax home, and some contractors pay it only on days worked. '
            'Ask the recruiter how many days a week it is paid and whether housing comes on top.</p>')


def travel_faq(jobs: list[dict]) -> list[tuple[str, str]]:
    j = example_job(jobs)
    week = (f" For example, {_usd(j['hourly_min'])}/hr on 72-hour weeks plus {_usd(j['per_diem'])}/day comes to about "
            f"{_usd(week_pay(j['hourly_min'], j['per_diem'])['total'])} a week before taxes." if j else "")
    return [
        ("How much do data center travel jobs pay?",
         "Traveling fiber and cabling techs usually earn an hourly rate with overtime after 40 hours, plus a daily per diem." + week),
        ("What is per diem on a data center job?",
         "A daily allowance for food and lodging when you work away from home, commonly $100–$200 a day. "
         "It is usually not taxed if you keep a tax home elsewhere, so it adds more to take-home pay than the same amount in wages."),
        ("Do I need experience for a data center travel job?",
         "Many traveling fiber and cabling roles ask for 6–12 months of experience, but contractors also hire helpers and Level I techs. "
         "See the entry-level jobs page for roles that take people with no experience."),
        ("What schedule do travel data center jobs work?",
         "Construction-side crews often work 6×10 or 6×12 for several weeks, then rotate home. Ask how long each rotation lasts and who pays the flights."),
    ]


if __name__ == "__main__":
    w = week_pay(27, 178)
    assert (w["straight"], w["overtime"], w["per_diem"], w["total"]) == (1080, 1296, 1246, 3622), w
    assert example_job([{"per_diem": 200, "hourly_min": 27}, {"per_diem": 178, "hourly_min": 27}])["per_diem"] == 178
    assert example_job([{"per_diem": 178}]) is None and travel_math_html([], str) == ""
    print("ok")
