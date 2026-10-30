"""Pruebas del recolector. Correr con: python -m pytest -q  (o python test_collector.py)"""
from datetime import date

import collector as c


def test_pay_parsing():
    assert c.parse_pay("The base salary range for this role is $65,000 to $83,000.") == (65000, 83000, "year")
    assert c.parse_pay("The base salary range for this role is $65.000 to $85,000.") == (65000, 85000, "year")
    assert c.parse_pay("$23 – $29 per hour • 12% Shift Differential") == (23, 29, "hour")
    assert c.parse_pay("$314K – $465K • Multiple Ranges") == (314000, 465000, "year")
    assert c.parse_pay("COMPENSATION AND BENEFITS: $68,400 - $102,600 USD Base salary") == (68400, 102600, "year")
    assert c.parse_pay("respond within 24-48 hours") == (None, None, "")
    assert c.parse_pay("") == (None, None, "")


def test_hourly_conversion():
    assert c.to_hourly(65000, "year") == 31.25
    assert c.to_hourly(30.91, "hour") == 30.91


def test_location():
    assert c.parse_location("Southaven, MS; Memphis, TN") == ("Southaven", "MS")
    assert c.parse_location("Arvada, CO - US") == ("Arvada", "CO")
    assert c.parse_location("Volo,IL") == ("Volo", "IL")
    assert c.parse_location("Wink, Texas, USA") == ("Wink", "TX")
    assert c.parse_location("Dublin, Ireland") == ("Dublin", "")
    assert c.parse_location("Remote - US") == ("Remote", "")


def test_title_filter():
    for t in ["Data Center Technician", "Engineering Operation Technician", "Critical Facilities Engineer - Memphis",
              "HVAC Technician - Memphis", "Medium Voltage Electrician (Service & Repair)", "Control Room Operator"]:
        assert c.is_tech_title(t), t
    for t in ["Construction Superintendent, Mechanical - Memphis", "Supervisor, Critical Facility Operations",
              "Staff Mechanical Engineer", "CNC Operator", "Assembly Technician", "Data Center Technician Manager",
              "Mechanical Quality Inspector", "Mechanical Engineer - Memphis"]:
        assert not c.is_tech_title(t), t


def test_level_and_role():
    assert c.classify_level("Fiber Technician III - Memphis") == "III"
    assert c.classify_level("Operations & Maintenance Technician II") == "II"
    assert c.classify_level("Senior Critical Facilities Technician") == "III"
    assert c.classify_level("Data Center Technician") == ""
    assert c.classify_role("Data Center Operations Technician") == "Técnico de data center (DCT)"
    assert c.classify_role("Engineering Operations Technician") == "Instalaciones críticas"
    assert c.classify_role("Turbine Technician - Memphis") == "Energía / generación"


def test_build_from_saved_sample():
    raw = {
        "amazon": [{"id": "1", "path": "/en/jobs/1/x", "t": "Data Center Technician", "loc": "Wink, Texas, USA",
                    "d": "October 29, 2026", "pay": ["30.91", "54.18", "hourly"]},
                   {"id": "2", "path": "/en/jobs/2/x", "t": "Data Center Technician Manager", "loc": "Wink, Texas, USA",
                    "d": "October 29, 2026", "pay": None}],
        "greenhouse": {"coreweave": [{"id": 9, "title": "Data Center Technician - Afton, TX",
                                      "location": {"name": "Afton, TX"}, "first_published": "2026-06-08T18:37:50-04:00",
                                      "pay_text": "The base salary range for this role is $65,000 to $83,000."}]},
        "ashby": {},
    }
    jobs = c.build(raw, date(2026, 10, 30))
    assert [j.company for j in jobs] == ["Amazon", "CoreWeave"]
    amz = jobs[0]
    assert (amz.city, amz.state, amz.hourly_min, amz.hourly_max, amz.days_posted) == ("Wink", "TX", 30.91, 54.18, 1)
    assert jobs[1].days_posted == 144


def test_greenhouse_pay_at_end_of_long_description():
    content = "&lt;p&gt;" + "Lorem ipsum. " * 500 + "The base salary range for this role is $65.000 to $85,000.&lt;/p&gt;"
    j = c.finalize(c.from_greenhouse("coreweave", "CoreWeave", {
        "id": 1, "title": "Data Center Technician - Chester, VA", "location": {"name": "Chester, VA"},
        "first_published": "2026-10-01T00:00:00Z", "content": content}))
    assert (j.pay_min, j.pay_max, j.pay_unit, j.state) == (65000, 85000, "year", "VA")


def test_contractor_filters_and_introl():
    # contratistas: entran los puestos de data center, no los de fibra/torres
    assert c.is_tech_title("Data Center Deployment Foreman I") and c.DC_TITLE.search("Data Center Deployment Foreman I")
    assert c.is_tech_title("Fiber Technician 1 - Travel") and not c.DC_TITLE.search("Fiber Technician 1 - Travel")
    assert not c.is_tech_title("Data Center Technician Manager")
    html = ('<a href="https://apply.appone.com/job/abc" class="job-card "><div class="job-card-content">'
            '<h3 class="job-title">Data Center Technician</h3><p class="job-location">San Antonio, TX</p>'
            '<div class="job-meta"><span class="job-salary">$30-$36/hr</span><span class="job-type">Temporary</span>'
            '</div></div></a>')
    rows = c.parse_introl(html)
    assert len(rows) == 1 and rows[0]["id"] == "introl-abc"
    j = c.build({"other": rows}, date(2026, 10, 30))[0]
    assert (j.company, j.city, j.state, j.hourly_min, j.hourly_max) == ("Introl", "San Antonio", "TX", 30.0, 36.0)
    assert c.ORACLE_PAY.search("from $27.64 to $56.83 per hour; from: $57,500").groups() == ("27.64", "56.83", "hour")


def test_keep_previous_if_source_failed():
    import json, tempfile
    from pathlib import Path
    prev = [{"source": "google", "company": "Google", "job_id": "g1", "title": "Data Center Technician",
             "city": "Midlothian", "state": "TX", "location_raw": "Midlothian, TX", "posted": "2026-10-20",
             "url": "https://example.com/g1", "hourly_min": 30.0, "hourly_max": 40.0, "openings": 1},
            {"source": "amazon", "company": "Amazon", "job_id": "old", "title": "Data Center Technician",
             "city": "Wink", "state": "TX", "location_raw": "Wink, TX", "posted": "2026-10-01",
             "url": "https://example.com/old", "openings": 1}]
    with tempfile.TemporaryDirectory() as d:
        p = Path(d) / "jobs.json"
        p.write_text(json.dumps(prev))
        live = [c.Job("amazon", "Amazon", "new", "Data Center Technician", "Wink", "TX", "Wink, TX",
                      "2026-10-29", "https://example.com/new")]
        out = c.keep_previous_if_source_failed(live, p, date(2026, 10, 30))
    # Amazon respondió hoy: no se conserva la vacante vieja de Amazon. Google falló: se conserva la de ayer.
    assert sorted((j.company, j.job_id) for j in out) == [("Amazon", "new"), ("Google", "g1")]
    assert [j for j in out if j.company == "Google"][0].days_posted == 10


if __name__ == "__main__":
    import sys
    fails = 0
    for name, fn in list(globals().items()):
        if name.startswith("test_"):
            try:
                fn(); print("ok  ", name)
            except AssertionError as e:
                fails += 1; print("FAIL", name, e)
    sys.exit(1 if fails else 0)
