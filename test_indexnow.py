"""Pruebas de indexnow.py (se corren en el workflow antes de publicar)."""
from indexnow import changed_urls, payload, sitemap_urls

OLD = "<urlset><url><loc>https://x.com/jobs/a.html</loc></url><url><loc>https://x.com/jobs/b.html</loc></url></urlset>"
NEW = "<urlset><url><loc>https://x.com/jobs/b.html</loc></url><url><loc>https://x.com/jobs/c.html</loc></url></urlset>"


def test_reads_every_loc():
    assert sitemap_urls(OLD) == {"https://x.com/jobs/a.html", "https://x.com/jobs/b.html"}


def test_sends_new_and_closed_jobs_only():
    assert changed_urls(OLD, NEW) == ["https://x.com/jobs/a.html", "https://x.com/jobs/c.html"]


def test_sends_nothing_without_previous_sitemap():
    assert changed_urls("", NEW) == []


def test_sends_nothing_when_unchanged():
    assert changed_urls(NEW, NEW) == []


def test_payload_points_to_hosted_key():
    p = payload(["https://datacenterjobusa.com/jobs/c.html"])
    assert p["host"] == "datacenterjobusa.com"
    assert p["keyLocation"] == f"https://datacenterjobusa.com/{p['key']}.txt"


if __name__ == "__main__":
    for name, fn in list(globals().items()):
        if name.startswith("test_"):
            fn()
    print("indexnow: todas las pruebas pasan")
