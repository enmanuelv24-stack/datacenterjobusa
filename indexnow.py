"""Avisa a Bing, Yandex y otros buscadores (protocolo IndexNow) de los empleos nuevos y cerrados del día.

Uso en el workflow:
  python indexnow.py diff --old <sitemap-jobs.xml publicado> --new site/sitemap-jobs.xml --out indexnow-urls.txt
  python indexnow.py submit --urls indexnow-urls.txt

La clave es pública por diseño: el sitio la sirve en /<clave>.txt para probar que el dominio es nuestro.
Solo se envían URL que cambiaron (nuevas o cerradas) para no reenviar páginas sin cambios.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
import urllib.error
import urllib.request
from pathlib import Path

from site_config import INDEXNOW_KEY, SITE_URL

ENDPOINT = "https://api.indexnow.org/indexnow"
MAX_URLS = 10_000  # límite del protocolo por envío
TIMEOUT_S = 30
LOC_RE = re.compile(r"<loc>([^<]+)</loc>")


def sitemap_urls(xml: str) -> set[str]:
    """Las URL <loc> de un sitemap."""
    return set(LOC_RE.findall(xml))


def changed_urls(old_xml: str, new_xml: str) -> list[str]:
    """URL nuevas o quitadas entre dos sitemaps, ordenadas. Sin sitemap anterior no envía nada."""
    old, new = sitemap_urls(old_xml), sitemap_urls(new_xml)
    if not old:
        return []
    return sorted(old ^ new)


def _read(source: str) -> str:
    if source.startswith("http"):
        try:
            with urllib.request.urlopen(source, timeout=TIMEOUT_S) as r:
                return r.read().decode("utf-8", "replace")
        except (urllib.error.URLError, TimeoutError) as e:
            print(f"No se pudo leer {source}: {e}", file=sys.stderr)
            return ""
    p = Path(source)
    return p.read_text(encoding="utf-8") if p.exists() else ""


def payload(urls: list[str]) -> dict:
    host = SITE_URL.split("//", 1)[1].rstrip("/")
    return {"host": host, "key": INDEXNOW_KEY, "keyLocation": f"{SITE_URL}/{INDEXNOW_KEY}.txt", "urlList": urls[:MAX_URLS]}


def submit(urls: list[str]) -> int:
    if not urls:
        print("IndexNow: nada nuevo que avisar")
        return 0
    req = urllib.request.Request(ENDPOINT, data=json.dumps(payload(urls)).encode(), method="POST",
                                 headers={"Content-Type": "application/json; charset=utf-8"})
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT_S) as r:
            print(f"IndexNow: {len(urls)} URL enviadas, respuesta {r.status}")
            return 0
    except urllib.error.HTTPError as e:
        # 202 = aceptado y pendiente de verificar la clave; cualquier otro código se registra sin romper la publicación
        print(f"IndexNow respondió {e.code}: {e.read()[:200]!r}", file=sys.stderr)
        return 0 if e.code == 202 else 1
    except (urllib.error.URLError, TimeoutError) as e:
        print(f"IndexNow no respondió: {e}", file=sys.stderr)
        return 1


def main() -> int:
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    d = sub.add_parser("diff")
    d.add_argument("--old", required=True)
    d.add_argument("--new", required=True)
    d.add_argument("--out", required=True)
    s = sub.add_parser("submit")
    s.add_argument("--urls", required=True)
    a = ap.parse_args()
    if a.cmd == "diff":
        urls = changed_urls(_read(a.old), _read(a.new))
        Path(a.out).write_text("\n".join(urls), encoding="utf-8")
        print(f"IndexNow: {len(urls)} URL cambiaron")
        return 0
    lines = Path(a.urls).read_text(encoding="utf-8").split() if Path(a.urls).exists() else []
    return submit(lines)


if __name__ == "__main__":
    sys.exit(main())
