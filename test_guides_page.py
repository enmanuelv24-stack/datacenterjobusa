"""Pruebas de la página de guías. Correr con: python test_guides_page.py"""
import guides_page as g


def test_links_only_guides_that_exist_on_the_site():
    page = g.guides_page({"certifications.html", "salaries.html"})

    assert 'href="certifications.html"' in page["body"]
    assert 'href="salaries.html"' in page["body"]
    assert "job-ready-kit.html" not in page["body"]


def test_page_has_path_title_and_description():
    page = g.guides_page(set())

    assert page["path"] == "guides.html"
    assert "Guides" in page["title"]
    assert page["desc"]


def test_every_guide_has_a_title_and_a_blurb():
    for path, title, blurb in g.GUIDES:
        assert path.endswith(".html") and title and blurb


if __name__ == "__main__":
    for name, fn in list(globals().items()):
        if name.startswith("test_"):
            fn()
    print("OK")
