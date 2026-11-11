"""Página en español (/es/): adonde llevan los videos de @empleosdatacenterusa y "Empleos Data Center USA".

Aquí van las cifras y los textos; build_site.py arma el HTML con sus piezas (lista de vacantes, tablas, formulario).
Solo cifras de las ofertas publicadas; nunca estimaciones.
"""
from __future__ import annotations

import statistics

ES_PATH = "es/index.html"


def _hr(v: float) -> str:
    return f"${v:,.2f}"


def summary(jobs: list[dict]) -> dict:
    """Vacantes, vacantes para principiantes, empresas y sueldo típico (mediana) de las ofertas para principiantes con sueldo."""
    entry = [j for j in jobs if j.get("entry")]
    paid = [j for j in entry if j.get("hourly_min")]
    return {
        "openings": sum(j["openings"] for j in jobs),
        "entry_openings": sum(j["openings"] for j in entry),
        "employers": len({j["company"] for j in jobs}),
        "lo": statistics.median(j["hourly_min"] for j in paid) if paid else None,
        "hi": statistics.median(j["hourly_max"] for j in paid) if paid else None,
    }


def lede(s: dict) -> str:
    pay = f" Sueldo típico publicado para principiantes: {_hr(s['lo'])}–{_hr(s['hi'])} la hora." if s["lo"] else ""
    return (f"Hoy hay {s['openings']:,} vacantes de técnico en data centers de {s['employers']} empresas en Estados Unidos. "
            f"{s['entry_openings']:,} aceptan gente sin experiencia en data centers.{pay} "
            "Cada oferta muestra el sueldo que publicó la empresa y el link directo para aplicar.")


def faq(entry_openings: int, s: dict) -> list[tuple[str, str]]:
    pay = (f"Para principiantes, lo típico es {_hr(s['lo'])}–{_hr(s['hi'])} la hora según las ofertas publicadas; "
           "los contratistas muchas veces pagan horas extra y viáticos aparte." if s.get("lo") else
           "Muchas empresas no publican el sueldo; pregunta al reclutador por la paga por hora, horas extra y viáticos.")
    return [
        ("¿Se puede trabajar en un data center sin experiencia?",
         f"Sí. Ahora mismo hay {entry_openings:,} vacantes para principiantes: técnicos Level I, instaladores de cable, "
         "técnicos de fibra y trabajos de construcción en data centers. La empresa entrena en el trabajo."),
        ("¿Cuánto paga un trabajo en un data center?", pay),
        ("¿Qué piden para entrar?",
         "Normalmente high school o GED, examen de drogas y revisión de antecedentes, poder cargar 50 libras, turnos de 10 a 12 horas "
         "y licencia de manejo. La tarjeta OSHA 10 ayuda en obras. Muchas ofertas piden leer y comunicarse en inglés."),
        ("¿Cuesta algo usar este sitio?",
         "No. Es gratis. No recibimos aplicaciones: cada oferta te lleva a la página de la empresa para aplicar directo."),
    ]


STEPS = [
    ("Elige un puesto de entrada", "Técnico de data center Level I, instalador de cable (cable puller), técnico de fibra o ayudante en construcción."),
    ("Saca tu OSHA 10", "Es un curso corto y barato en línea que muchas obras piden o prefieren."),
    ("Aplica directo a la empresa", "Cada oferta tiene el link a la página de la empresa. Revisa el sueldo antes de aplicar."),
]
