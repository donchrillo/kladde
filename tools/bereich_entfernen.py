#!/usr/bin/env python3
"""Löscht einen Bereich samt allem, was daran hängt.

    python tools/bereich_entfernen.py --bereich anna-muster

Gedacht für genau einen Fall: den **gefüllten privaten Bereich** eines
ausgeschiedenen Kollegen. Über die API geht das nicht, und das ist Absicht —
private Bereiche sind für Administratoren verschlossen, und `DELETE
/api/spaces/{key}` verlangt wie überall einen leeren Bereich.

Einen privaten Bereich an einen Nachfolger zu übertragen, gibt es bewusst nicht
mehr: wer übertragen darf, kann sich selbst eintragen, lesen und zurücktragen —
damit wäre "privat" nur noch eine Bitte. Bleibt also das Löschen, und dieses
Werkzeug zeigt dabei **nie den Inhalt**, sondern nur Name, Eigentümer und
Zahlen, und fragt vorher nach.

Gelöscht werden: der Bereich, seine Seiten, deren Revisionen, Anhänge (auch die
Dateien unter ATTACHMENT_DIR), Verweise, Schlagwortzuordnungen, Freigaben und
die Einträge im Volltextindex.

Danach: `sudo systemctl restart kladde-backend` ist nicht nötig — das Backend
liest die Datenbank bei jeder Anfrage neu.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

WURZEL = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(WURZEL / "backend"))

from src.config import get_settings  # noqa: E402
from src.database import SessionLocal  # noqa: E402
from src.models import Page, Space, User  # noqa: E402
from src.search import aus_index_entfernen  # noqa: E402


def main() -> None:
    zerleger = argparse.ArgumentParser(description=__doc__)
    zerleger.add_argument("--bereich", required=True, help="Bereichsschlüssel, z. B. anna-muster")
    zerleger.add_argument(
        "--ja",
        action="store_true",
        help="Rückfrage überspringen (für Skripte; sonst wird interaktiv gefragt)",
    )
    argumente = zerleger.parse_args()

    with SessionLocal() as db:
        space = db.query(Space).filter(Space.key == argumente.bereich).one_or_none()
        if space is None:
            raise SystemExit(f"Kein Bereich mit dem Schlüssel '{argumente.bereich}'.")

        seiten = db.query(Page).filter(Page.space_id == space.id).all()
        anhaenge = [anhang for seite in seiten for anhang in seite.attachments]
        eigentuemer = db.get(User, space.owner_id) if space.owner_id is not None else None

        print(f"Bereich:     {space.name} ({space.key})")
        print(f"Art:         {'privat' if space.is_private else 'offen'}")
        if eigentuemer is not None:
            print(f"Eigentümer:  {eigentuemer.display_name} ({eigentuemer.username})")
        print(f"Seiten:      {len(seiten)}")
        print(f"Anhänge:     {len(anhaenge)}")
        print("Titel und Inhalte werden bewusst nicht angezeigt.")

        if not argumente.ja:
            if not sys.stdin.isatty():
                raise SystemExit("Ohne Terminal bitte --ja mitgeben.")
            if input(f"\nWirklich unwiderruflich löschen? Tippe '{space.key}': ") != space.key:
                raise SystemExit("Abgebrochen, nichts geändert.")

        # Erst die Dateien von der Platte: die Anhang-Zeilen verschwinden per
        # Cascade, ihre Dateien nicht.
        ablage = Path(get_settings().attachment_dir)
        for anhang in anhaenge:
            (ablage / anhang.stored_name).unlink(missing_ok=True)

        for seite in seiten:
            aus_index_entfernen(db, seite.id)
        # Erst den Baum flach machen, dann löschen: sonst hinge die Reihenfolge
        # daran, welche Seite zufällig vor ihrem Elternteil drankommt.
        for seite in seiten:
            seite.parent_id = None
        db.flush()
        for seite in seiten:
            db.delete(seite)  # Revisionen, Anhänge, Verweise, Etiketten per Cascade
        db.flush()
        db.delete(space)  # Freigaben per Cascade
        db.commit()

    print(f"Bereich '{argumente.bereich}' und {len(seiten)} Seiten gelöscht.")


if __name__ == "__main__":
    main()
