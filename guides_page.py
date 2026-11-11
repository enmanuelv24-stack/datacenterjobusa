"""Página índice de guías: un solo lugar con todo lo que ayuda a conseguir el trabajo (antes eran 5 enlaces sueltos en el menú)."""
import html

from site_config import SITE_NAME

E = html.escape
PATH = "guides.html"

# (archivo, título, para qué sirve)
GUIDES = [
    ("how-to-become-a-data-center-technician.html", "How to become a data center technician",
     "The path in with no degree and no experience, step by step."),
    ("entry-level-jobs.html", "Entry-level jobs",
     "Open jobs that take beginners, and what they pay."),
    ("data-center-technician-resume.html", "Résumé guide",
     "What to put on a technician résumé, whatever your background."),
    ("data-center-technician-interview-questions.html", "Interview questions",
     "The questions hiring managers ask technicians, with answers."),
    ("certifications.html", "Certifications",
     "Which certifications employers ask for and which to skip."),
    ("shift-schedules.html", "Shift schedules",
     "12-hour rotations, nights and 6×10s: what each schedule means."),
    ("travel-jobs.html", "Per diem and travel jobs",
     "Jobs that mention per diem or housing, and how travel work pays."),
    ("salaries.html", "Technician salaries",
     "Posted pay by level, company and state."),
    ("military-veteran-data-center-jobs.html", "Military and SkillBridge",
     "How veterans move into data center work."),
    ("job-ready-kit.html", "Job-Ready Kit",
     "Everything above in one PDF, with a 30-day plan and templates."),
]


def guides_page(existing_paths: set[str]) -> dict:
    """Devuelve la página de guías. Solo enlaza las guías que el sitio realmente generó."""
    cards = "".join(f'<li><a href="{E(path)}"><b>{E(title)}</b><span>{E(blurb)}</span></a></li>'
                    for path, title, blurb in GUIDES if path in existing_paths)
    body = ('<p class="crumbs"><a href="index.html">Jobs</a> / Guides</p>'
            '<h1>Guides for getting the job</h1>'
            '<p class="lede">Written by a working data center technician. Free, no sign-up needed.</p>'
            f'<ul class="guides">{cards}</ul>')
    return {"path": PATH, "title": f"Data Center Technician Guides: Getting Hired, Pay and Schedules | {SITE_NAME}",
            "desc": "Free guides for data center technicians: how to get in with no experience, résumé, interview questions, certifications, shifts and pay.",
            "body": body}
