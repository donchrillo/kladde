#!/usr/bin/env python3
"""Kleiner Client für dieses Wiki — nur Standardbibliothek.

Zugang in ~/.config/wiki/zugang (JSON, chmod 600), anderer Ort über WIKI_ZUGANG:
    {"url": "https://pn40.local", "username": "claude", "password": "..."}
Die Datei liest nur dieses Skript. Das Session-Cookie liegt in ~/.cache/wiki/cookie.

Befehle:
  bereiche                                   Bereiche auflisten (id, key, name)
  baum <bereich-key>                         Seitenbaum eines Bereichs (id, parent, Titel)
  suche <text> [--bereich-id N]              Volltextsuche
  lesen <seiten-id>                          Seite als JSON (inkl. body)
  anlegen --bereich-id N --titel T --datei F [--eltern-id P]
  aendern <seiten-id> [--titel T] [--datei F] [--eltern-id P]
"""

import argparse
import http.cookiejar
import json
import os
import ssl
import sys
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

ZUGANG = Path(os.environ.get("WIKI_ZUGANG", Path.home() / ".config/wiki/zugang"))
COOKIE = Path.home() / ".cache/wiki/cookie"


def _zugang() -> dict:
    if not ZUGANG.exists():
        sys.exit(f"Zugangsdatei fehlt: {ZUGANG} (JSON mit url/username/password, chmod 600)")
    return json.loads(ZUGANG.read_text())


_URL = os.environ.get("WIKI_URL") or _zugang().get("url")
if not _URL:
    sys.exit(f'Keine Wiki-Adresse: "url" in {ZUGANG} eintragen oder WIKI_URL setzen')
BASE = _URL.rstrip("/") + "/api"

# Caddy `tls internal` — die interne CA ist nicht überall im Python-Truststore.
_ctx = ssl.create_default_context()
_ctx.check_hostname = False
_ctx.verify_mode = ssl.CERT_NONE

COOKIE.parent.mkdir(parents=True, exist_ok=True)
_jar = http.cookiejar.MozillaCookieJar(str(COOKIE))
if COOKIE.exists():
    _jar.load(ignore_discard=True, ignore_expires=True)
_op = urllib.request.build_opener(
    urllib.request.HTTPCookieProcessor(_jar), urllib.request.HTTPSHandler(context=_ctx)
)


def _roh(methode: str, pfad: str, daten: dict | None = None):
    req = urllib.request.Request(
        BASE + pfad,
        method=methode,
        data=json.dumps(daten).encode() if daten is not None else None,
        headers={"Content-Type": "application/json"},
    )
    with _op.open(req) as antwort:
        inhalt = antwort.read()
    return json.loads(inhalt) if inhalt else None


def _anmelden() -> None:
    z = _zugang()
    _roh("POST", "/auth/login", {"username": z["username"], "password": z["password"]})
    _jar.save(ignore_discard=True, ignore_expires=True)
    COOKIE.chmod(0o600)


def api(methode: str, pfad: str, daten: dict | None = None):
    """Ruft die API auf; bei 401 einmal neu anmelden und wiederholen."""
    try:
        return _roh(methode, pfad, daten)
    except urllib.error.HTTPError as fehler:
        if fehler.code != 401:
            sys.exit(f"HTTP {fehler.code}: {fehler.read().decode(errors='replace')}")
    _anmelden()
    try:
        return _roh(methode, pfad, daten)
    except urllib.error.HTTPError as fehler:
        sys.exit(f"HTTP {fehler.code}: {fehler.read().decode(errors='replace')}")


def main() -> None:
    p = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    sub = p.add_subparsers(dest="befehl", required=True)
    sub.add_parser("bereiche")
    b = sub.add_parser("baum")
    b.add_argument("key")
    s = sub.add_parser("suche")
    s.add_argument("text")
    s.add_argument("--bereich-id", type=int)
    le = sub.add_parser("lesen")
    le.add_argument("id", type=int)
    a = sub.add_parser("anlegen")
    a.add_argument("--bereich-id", type=int, required=True)
    a.add_argument("--titel", required=True)
    a.add_argument("--datei", required=True)
    a.add_argument("--eltern-id", type=int)
    ae = sub.add_parser("aendern")
    ae.add_argument("id", type=int)
    ae.add_argument("--titel")
    ae.add_argument("--datei")
    ae.add_argument("--eltern-id", type=int)
    arg = p.parse_args()

    if arg.befehl == "bereiche":
        for r in api("GET", "/spaces"):
            print(r["id"], r["key"], r["name"], sep="\t")
    elif arg.befehl == "baum":

        def ausgeben(knoten: list, tiefe: int = 0) -> None:
            for r in knoten:
                print(r["id"], r["parent_id"], "  " * tiefe + r["title"], sep="\t")
                ausgeben(r.get("children", []), tiefe + 1)

        ausgeben(api("GET", f"/spaces/{arg.key}/pages"))
    elif arg.befehl == "suche":
        q = {"q": arg.text}
        if arg.bereich_id:
            q["space_id"] = arg.bereich_id
        for r in api("GET", "/search?" + urllib.parse.urlencode(q)):
            print(r["page_id"], r["space_key"], r["title"], sep="\t")
    elif arg.befehl == "lesen":
        print(json.dumps(api("GET", f"/pages/{arg.id}"), ensure_ascii=False, indent=2))
    elif arg.befehl == "anlegen":
        d = api(
            "POST",
            "/pages",
            {
                "space_id": arg.bereich_id,
                "title": arg.titel,
                "parent_id": arg.eltern_id,
                "body": Path(arg.datei).read_text(encoding="utf-8"),
            },
        )
        print(d["id"], d["slug"], d["title"], sep="\t")
    elif arg.befehl == "aendern":
        daten = {}
        if arg.titel:
            daten["title"] = arg.titel
        if arg.datei:
            daten["body"] = Path(arg.datei).read_text(encoding="utf-8")
        if arg.eltern_id is not None:
            daten["parent_id"] = arg.eltern_id
        d = api("PATCH", f"/pages/{arg.id}", daten)
        print(d["id"], d["slug"], d["title"], sep="\t")


if __name__ == "__main__":
    main()
