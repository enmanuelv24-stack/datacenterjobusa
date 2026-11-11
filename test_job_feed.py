"""Pruebas del feed XML para agregadores. Correr con: python test_job_feed.py"""
import xml.etree.ElementTree as ET
from datetime import date

import job_feed as f

JOBS = [
    {"slug": "amazon-dct-wharton-tx", "title": "Data Center Technician", "company": "Amazon", "job_id": "123",
     "city": "Wharton", "state": "TX", "posted": "2026-11-05", "hourly_min": 27.98, "hourly_max": 48.99,
     "summary": "Install and repair servers. Pay ]]> tricky text.", "role": "dct"},
    {"slug": "oracle-tech-or", "title": "Technician", "company": "Oracle", "job_id": "9", "city": "", "state": "OR",
     "posted": None, "hourly_min": None, "hourly_max": None, "summary": "", "role": "x"},
]


def _feed():
    xml = f.job_feed_xml(JOBS, "https://datacenterjobusa.com", "Data Center Job USA", date(2026, 11, 9),
                         title_of=lambda t: t.strip(), role_name=lambda r: {"dct": "Data center technician"}.get(r, "Other technician"))
    return ET.fromstring(xml)


def test_feed_is_valid_xml_with_one_job_per_listing():
    root = _feed()
    assert root.tag == "source"
    assert len(root.findall("job")) == 2


def test_links_point_to_our_pages_with_utm():
    url = _feed().find("job/url").text
    assert url == "https://datacenterjobusa.com/jobs/amazon-dct-wharton-tx.html?utm_source=jobfeed&utm_medium=aggregator"


def test_pay_only_when_posted_and_cdata_is_escaped():
    jobs = _feed().findall("job")
    assert jobs[0].find("salary").text == "$27.98 - $48.99 per hour"
    assert "]]> tricky" in jobs[0].find("description").text
    assert jobs[1].find("salary") is None
    assert jobs[1].find("description").text == "Technician at Oracle in OR."


def test_feed_prefers_full_description_over_summary():
    jobs = [dict(JOBS[0], description="Full duties: rack servers. Requirements: A+ certification.")]
    xml = f.job_feed_xml(jobs, "https://datacenterjobusa.com", "Data Center Job USA", date(2026, 11, 9),
                         title_of=lambda t: t, role_name=lambda r: r)
    desc = ET.fromstring(xml).find("job/description").text
    assert "Requirements: A+ certification." in desc
    assert desc.startswith("Posted pay: $27.98 - $48.99 per hour.")


if __name__ == "__main__":
    for name, fn in list(globals().items()):
        if name.startswith("test_"):
            fn()
            print("ok  ", name)
