#!/usr/bin/env python3
"""Legt einen Administrator an oder setzt sein Passwort zurück.

    python tools/admin_anlegen.py --benutzer anna --name "Anna Beispiel"

Das Passwort wird zweimal abgefragt und nie als Argument übergeben (sonst
stünde es in der Shell-History und in der Prozessliste).

Dieses Werkzeug schreibt als einziges **direkt in die Datenbank**. Das ist
Absicht: Es wird genau dann gebraucht, wenn es noch kein Konto gibt, mit dem
man sich anmelden könnte — vor dem ersten Einschalten von `AUTH_ENABLED`, oder
wenn man sich ausgesperrt hat. Es fasst nur die Tabelle `user` an, also weder
Suchindex noch Verweise; ein Umweg über die API ist deshalb nicht nötig.

Danach:

    AUTH_ENABLED=true in .env setzen
    sudo systemctl restart kladde-backend
"""

from __future__ import annotations

import argparse
import getpass
import sys
from pathlib import Path

WURZEL = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(WURZEL / "backend"))

from src.database import SessionLocal  # noqa: E402
from src.models import User  # noqa: E402
from src.passwoerter import hash_erzeugen  # noqa: E402

MINDESTLAENGE = 8


def passwort_abfragen() -> str:
    """Fragt das Passwort zweimal ab und gibt es erst zurück, wenn es passt.

    Ohne echtes Terminal (Pipe, `!`-Modus in Claude Code, Skript) gibt es keine
    verdeckte Eingabe — dann wird eine Zeile von der Standardeingabe gelesen:

        printf 'meinpasswort' | python tools/admin_anlegen.py --benutzer anna
    """
    if not sys.stdin.isatty():
        aus_pipe = sys.stdin.readline().strip()
        if len(aus_pipe) < MINDESTLAENGE:
            raise SystemExit(
                f"Passwort aus der Standardeingabe ist zu kurz (mind. {MINDESTLAENGE} Zeichen)."
            )
        return aus_pipe

    while True:
        erstes = getpass.getpass("Passwort: ")
        if len(erstes) < MINDESTLAENGE:
            print(f"Mindestens {MINDESTLAENGE} Zeichen, bitte noch einmal.")
            continue
        if erstes != getpass.getpass("Passwort wiederholen: "):
            print("Die beiden Eingaben stimmen nicht überein, bitte noch einmal.")
            continue
        return erstes


def main() -> None:
    zerleger = argparse.ArgumentParser(description=__doc__)
    zerleger.add_argument("--benutzer", required=True, help="Anmeldename, z. B. anna")
    zerleger.add_argument("--name", help="Anzeigename; ohne Angabe wie --benutzer")
    zerleger.add_argument(
        "--kein-admin",
        action="store_true",
        help="Konto ohne Administratorrechte anlegen (Freigaben dann einzeln vergeben)",
    )
    argumente = zerleger.parse_args()

    passwort = passwort_abfragen()

    with SessionLocal() as db:
        nutzer = db.query(User).filter(User.username == argumente.benutzer).one_or_none()
        if nutzer is None:
            nutzer = User(
                username=argumente.benutzer,
                display_name=argumente.name or argumente.benutzer,
                is_admin=not argumente.kein_admin,
            )
            db.add(nutzer)
            was = "angelegt"
        else:
            # Bestehendes Konto: Passwort zurücksetzen und wieder freischalten.
            if argumente.name:
                nutzer.display_name = argumente.name
            nutzer.is_active = True
            if not argumente.kein_admin:
                nutzer.is_admin = True
            was = "aktualisiert"

        nutzer.password_hash = hash_erzeugen(passwort)
        db.commit()
        # Offene Sitzungen dieses Kontos beenden — ein zurückgesetztes Passwort
        # soll auch bedeuten, dass alte Anmeldungen nicht weiterlaufen.
        for sitzung in list(nutzer.sessions):
            db.delete(sitzung)
        db.commit()

        rolle = "Benutzer" if argumente.kein_admin else "Administrator"
        print(f"{rolle} '{nutzer.username}' {was} (id={nutzer.id}).")

    print("Falls noch nicht geschehen: AUTH_ENABLED=true in .env, dann Backend neu starten.")


if __name__ == "__main__":
    main()
