"""XML job feed (Indeed-style <source><job>…) for job aggregators such as Jooble, Talent.com, Adzuna,
Careerjet and Jobrapido. They list our jobs and link back to our job pages, which brings visitors and links.

Every job links to its page on this site (not straight to the employer), tagged with utm_source=jobfeed so
the visits show up as their own channel in Analytics.
"""
from __future__ import annotations

from datetime import date, datetime
from email.utils import format_datetime
from pathlib import Path

FEED_NAME = "jobs-feed.xml"
UTM = "utm_source=jobfeed&utm_medium=aggregator"


def _cdata(text: str) -> str:
    return "<![CDATA[" + (text or "").replace("]]>", "]]]]><![CDATA[>") + "]]>"


def _salary(j: dict) -> str:
    if not j.get("hourly_min"):
        return ""
    lo, hi = j["hourly_min"], j.get("hourly_max") or j["hourly_min"]
    return f"${lo:,.2f} - ${hi:,.2f} per hour"


def _date(posted: str | None, today: date) -> str:
    d = date.fromisoformat(posted) if posted else today
    return format_datetime(datetime(d.year, d.month, d.day, 12, 0))


def job_feed_xml(jobs: list[dict], site_url: str, site_name: str, today: date, title_of, role_name) -> str:
    """Builds the feed. `title_of` cleans a job title; `role_name` maps the collector category to English."""
    rows = []
    for j in jobs:
        url = f"{site_url}/jobs/{j['slug']}.html?{UTM}"
        desc = j.get("description") or j.get("summary") or f"{title_of(j['title'])} at {j['company']} in {j.get('city') or j['state']}."
        pay = _salary(j)
        if pay:
            desc = f"Posted pay: {pay}. " + desc
        rows.append(
            "<job>"
            f"<title>{_cdata(title_of(j['title']))}</title>"
            f"<date>{_cdata(_date(j.get('posted'), today))}</date>"
            f"<referencenumber>{_cdata(j['company'] + '-' + str(j['job_id']))}</referencenumber>"
            f"<url>{_cdata(url)}</url>"
            f"<company>{_cdata(j['company'])}</company>"
            f"<city>{_cdata(j.get('city') or '')}</city>"
            f"<state>{_cdata(j['state'])}</state>"
            "<country><![CDATA[US]]></country>"
            f"<description>{_cdata(desc)}</description>"
            + (f"<salary>{_cdata(pay)}</salary>" if pay else "")
            + "<jobtype><![CDATA[fulltime]]></jobtype>"
            f"<category>{_cdata(role_name(j.get('role') or ''))}</category>"
            "</job>"
        )
    return ('<?xml version="1.0" encoding="utf-8"?><source>'
            f"<publisher>{_cdata(site_name)}</publisher><publisherurl>{_cdata(site_url)}</publisherurl>"
            f"<lastBuildDate>{_cdata(format_datetime(datetime(today.year, today.month, today.day, 6, 0)))}</lastBuildDate>"
            + "".join(rows) + "</source>")


def write_job_feed(out: Path, jobs: list[dict], site_url: str, site_name: str, today: date, title_of, role_name) -> Path:
    path = out / FEED_NAME
    path.write_text(job_feed_xml(jobs, site_url, site_name, today, title_of, role_name), encoding="utf-8")
    return path
