"""Interne Wiki-Verweise aus dem Markdown ableiten.

Ein interner Link sieht im gespeicherten Markdown so aus:

    [Drucker einrichten](/wiki/it-buero/drucker-einrichten)

Das Frontend erzeugt diese Form beim Verlinken und fängt sie beim Klick ab, statt
den Browser navigieren zu lassen. Für das Backend ist sie schlicht ein Muster,
aus dem sich Bereichsschlüssel und Slug lesen lassen — daraus entsteht die
`page_link`-Tabelle, die „wer verlinkt hierher?" ohne Volltextsuche beantwortet.
"""

import re

from sqlalchemy import select
from sqlalchemy.orm import Session

from .models import Page, PageLink, Space

# [Beschriftung](/wiki/<bereich>/<slug>) — Beschriftung interessiert hier nicht.
_LINK = re.compile(r"\]\(/wiki/([A-Za-z0-9_-]+)/([A-Za-z0-9_-]+)\)")


def ziel_ids(markdown: str, db: Session) -> set[int]:
    """IDs aller Seiten, auf die dieser Text intern verweist."""
    ids: set[int] = set()
    for space_key, slug in _LINK.findall(markdown):
        treffer = db.scalar(
            select(Page.id)
            .join(Space, Page.space_id == Space.id)
            .where(Space.key == space_key, Page.slug == slug)
        )
        if treffer is not None:
            ids.add(treffer)
    return ids


def links_aktualisieren(seite: Page, db: Session) -> None:
    """Schreibt die ausgehenden Verweise der Seite neu.

    Wird nach jeder inhaltlichen Änderung aufgerufen. Verweise auf die eigene
    Seite werden verworfen — sie wären in den Rückverweisen nur Rauschen.
    """
    gewuenscht = ziel_ids(seite.body, db) - {seite.id}
    vorhanden = {
        link.target_page_id: link
        for link in db.scalars(select(PageLink).where(PageLink.source_page_id == seite.id))
    }

    for ziel in gewuenscht - vorhanden.keys():
        db.add(PageLink(source_page_id=seite.id, target_page_id=ziel))
    for ziel in vorhanden.keys() - gewuenscht:
        db.delete(vorhanden[ziel])


def verweise_umschreiben(
    db: Session,
    aenderungen: dict[int, tuple[str, str]],
    lesbare_space_ids: list[int] | None = None,
) -> list[Page]:
    """Schreibt interne Verweise um, wenn Seiten ihre Adresse gewechselt haben.

    Ein Verweis trägt Bereichsschlüssel und Slug im Text (`/wiki/it-buero/vpn`).
    Wandert eine Seite in einen anderen Bereich, zeigen alle Verweise auf sie
    ins Leere — die `page_link`-Zeilen bleiben zwar richtig, weil sie auf IDs
    gehen, der Text aber nicht.

    `aenderungen` bildet die Seiten-ID auf (alter Pfad, neuer Pfad) ab. Betroffen
    sind alle Seiten, die laut `page_link` auf eine davon verweisen — auch die
    verschobenen selbst, denn sie verlinken sich oft untereinander. Gibt die
    geänderten Seiten zurück, damit der Aufrufer sie neu indexieren und je eine
    Revision anlegen kann.

    `lesbare_space_ids` grenzt ein, in welchen Bereichen überhaupt geschrieben
    werden darf (`None` heißt: in allen). Ohne diese Grenze schriebe ein Umzug
    in Seiten fremder Privatbereiche — der Eigentümer bekäme eine Änderung, die
    er nicht veranlasst hat, von jemandem, der seinen Bereich nicht einmal
    öffnen darf. Bleibt ein Verweis dort stehen, zeigt er auf die alte Adresse
    und läuft ins Leere; das ist der bewusst gewählte kleinere Schaden, und die
    Seite selbst findet sich weiterhin über Suche und Seitenbaum.
    """
    if not aenderungen:
        return []

    quellen = set(
        db.scalars(select(PageLink.source_page_id).where(PageLink.target_page_id.in_(aenderungen)))
    )
    abfrage = select(Page).where(Page.id.in_(quellen))
    if lesbare_space_ids is not None:
        abfrage = abfrage.where(Page.space_id.in_(lesbare_space_ids))
    geaendert: list[Page] = []
    for seite in db.scalars(abfrage):
        neu = seite.body
        for alt, jetzt in aenderungen.values():
            neu = neu.replace(f"]({alt})", f"]({jetzt})")
        if neu != seite.body:
            seite.body = neu
            geaendert.append(seite)
    return geaendert
