"""Pruebas de la ficha de vacante. Correr con: python test_job_page.py"""
import job_page as p


def test_pay_hero_shows_hourly_first_and_yearly_when_posted_per_year():
    job = {"hourly_min": 66.97, "hourly_max": 100.0, "pay_unit": "year", "pay_min": 139300, "pay_max": 208000}

    out = p.pay_hero(job)

    assert "$66.97–$100.00" in out
    assert "per hour · $139,300–$208,000 per year" in out


def test_pay_hero_hourly_job_has_no_yearly_figure():
    out = p.pay_hero({"hourly_min": 25.19, "hourly_max": 44.08, "pay_unit": "hour", "pay_min": 25.19, "pay_max": 44.08})

    assert "$25.19–$44.08" in out
    assert "per year" not in out


def test_pay_hero_says_so_when_pay_is_not_posted():
    out = p.pay_hero({"hourly_min": None, "hourly_max": None})

    assert "Pay not posted" in out
    assert "$" not in out


def test_posted_label_is_human_readable():
    assert p.posted_label("2026-11-04") == "Nov 4, 2026"


def test_posted_label_is_a_dash_without_a_valid_date():
    assert p.posted_label(None) == "—"
    assert p.posted_label("soon") == "—"


def test_description_turns_runs_of_short_lines_into_bullets():
    long_line = "You will keep the power and cooling plant running. " * 5
    text = f"{long_line}\nInstall and test fiber\nRack and stack servers\nLift 50 lb"

    out = p.description_html(text)

    assert out.startswith("<p>You will keep")
    assert "<ul><li>Install and test fiber</li><li>Rack and stack servers</li><li>Lift 50 lb</li></ul>" in out


def test_description_keeps_a_single_short_line_as_a_paragraph():
    assert p.description_html("Nights, 12-hour shifts.") == "<p>Nights, 12-hour shifts.</p>"


def test_description_escapes_markup_and_handles_empty_text():
    assert p.description_html("Use <b>PPE</b> & tools") == "<p>Use &lt;b&gt;PPE&lt;/b&gt; &amp; tools</p>"
    assert p.description_html("") == ""


if __name__ == "__main__":
    for name, fn in list(globals().items()):
        if name.startswith("test_"):
            fn()
    print("OK")
