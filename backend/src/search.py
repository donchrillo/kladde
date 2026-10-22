"""Volltextsuche über Seitentitel und -inhalt.

Unter SQLite (dem Normalfall hier) läuft die Suche über eine FTS5-Tabelle.
Bewusst eine eigenständige Tabelle statt einer `external content`-Variante mit
Triggern: der Index wird von der Anwendung gepflegt (`indexieren` /
`aus_index_entfernen`), was in den Tests dieselbe Codepfade nutzt wie im Betrieb
und ohne DB-seitige Trigger auskommt.

Läuft das Wiki später auf PostgreSQL, gibt es FTS5 nicht — dann greift
automatisch die `LIKE`-Rückfallebene. Die ist langsamer, liefert aber dieselbe
Struktur, sodass die API sich nicht unterscheidet.
"""

import re

from sqlalchemy import DDL, Row, event, text
from sqlalchemy.orm import Session

from .database import Base
from .models import Page

# Eigenständige FTS5-Tabelle. `page_id` ist UNINDEXED: sie wird nur
# zurückgegeben, nicht durchsucht.
_FTS_DDL = DDL("""
    CREATE VIRTUAL TABLE IF NOT EXISTS page_fts
    USING fts5(page_id UNINDEXED, title, body, tokenize='unicode61')
    """)

# An die Metadaten hängen, damit `create_all` (Tests) die Tabelle mit anlegt.
# Die Migration legt sie im Betrieb an. `execute_if` verhindert den Versuch auf
# anderen Datenbanken, die FTS5 nicht kennen.
event.listen(Base.metadata, "after_create", _FTS_DDL.execute_if(dialect="sqlite"))


def ist_fts_verfuegbar(db: Session) -> bool:
    """True, wenn die FTS5-Tabelle in dieser Datenbank existiert."""
    if db.bind is None or db.bind.dialect.name != "sqlite":
        return False
    treffer = db.execute(
        text("SELECT name FROM sqlite_master WHERE type='table' AND name='page_fts'")
    ).first()
    return treffer is not None


def indexieren(db: Session, seite: Page) -> None:
    """Schreibt den aktuellen Stand der Seite in den Suchindex."""
    if not ist_fts_verfuegbar(db):
        return
    aus_index_entfernen(db, seite.id)
    db.execute(
        text("INSERT INTO page_fts (page_id, title, body) VALUES (:pid, :title, :body)"),
        {"pid": seite.id, "title": seite.title, "body": seite.body},
    )


def aus_index_entfernen(db: Session, page_id: int) -> None:
    """Entfernt eine Seite aus dem Suchindex."""
    if not ist_fts_verfuegbar(db):
        return
    db.execute(text("DELETE FROM page_fts WHERE page_id = :pid"), {"pid": page_id})


def index_neu_aufbauen(db: Session) -> int:
    """Baut den Index aus den Seiten neu auf; gibt die Anzahl der Seiten zurück."""
    if not ist_fts_verfuegbar(db):
        return 0
    db.execute(text("DELETE FROM page_fts"))
    seiten = db.query(Page).all()
    for seite in seiten:
        db.execute(
            text("INSERT INTO page_fts (page_id, title, body) VALUES (:pid, :title, :body)"),
            {"pid": seite.id, "title": seite.title, "body": seite.body},
        )
    db.commit()
    return len(seiten)


# Wortzeichen inklusive Umlauten; alles andere trennt Suchbegriffe.
_WORT = re.compile(r"\w+", re.UNICODE)


def _fts_ausdruck(suche: str) -> str:
    """Übersetzt die Nutzereingabe in einen sicheren FTS5-Ausdruck.

    Jedes Wort wird in Anführungszeichen gesetzt und mit `*` als Präfix gesucht.
    Damit können Sonderzeichen der FTS5-Syntax (`"`, `*`, `NEAR`, `OR`) aus der
    Eingabe die Abfrage nicht verändern, und "druck" findet auch "Drucker".
    """
    woerter = _WORT.findall(suche)
    return " ".join(f'"{wort}"*' for wort in woerter)


def suche_fts(db: Session, begriff: str, space_ids: list[int] | None, limit: int) -> list[Row]:
    """FTS5-Suche. Liefert Zeilen mit page_id, Titel-Treffer und Textausschnitt."""
    ausdruck = _fts_ausdruck(begriff)
    if not ausdruck:
        return []

    # snippet(): Spalte 2 ist `body`; 12 Token Kontext um den Treffer.
    sql = """
        SELECT f.page_id AS page_id,
               snippet(page_fts, 2, '[[', ']]', ' … ', 12) AS ausschnitt
        FROM page_fts f
        JOIN page p ON p.id = f.page_id
        WHERE page_fts MATCH :ausdruck
        {bereichsfilter}
        ORDER BY rank
        LIMIT :limit
    """
    parameter: dict[str, object] = {"ausdruck": ausdruck, "limit": limit}
    bereichsfilter = ""
    if space_ids is not None:
        if not space_ids:
            return []
        platzhalter = ", ".join(f":s{i}" for i in range(len(space_ids)))
        bereichsfilter = f"AND p.space_id IN ({platzhalter})"
        parameter.update({f"s{i}": sid for i, sid in enumerate(space_ids)})

    return list(db.execute(text(sql.format(bereichsfilter=bereichsfilter)), parameter))


def suche_like(db: Session, begriff: str, space_ids: list[int] | None, limit: int) -> list[Row]:
    """Rückfallebene ohne FTS5: einfache Teilstringsuche in Titel und Text."""
    muster = f"%{begriff.strip()}%"
    if not begriff.strip():
        return []

    sql = """
        SELECT p.id AS page_id, substr(p.body, 1, 200) AS ausschnitt
        FROM page p
        WHERE (p.title LIKE :muster OR p.body LIKE :muster)
        {bereichsfilter}
        ORDER BY p.updated_at DESC
        LIMIT :limit
    """
    parameter: dict[str, object] = {"muster": muster, "limit": limit}
    bereichsfilter = ""
    if space_ids is not None:
        if not space_ids:
            return []
        platzhalter = ", ".join(f":s{i}" for i in range(len(space_ids)))
        bereichsfilter = f"AND p.space_id IN ({platzhalter})"
        parameter.update({f"s{i}": sid for i, sid in enumerate(space_ids)})

    return list(db.execute(text(sql.format(bereichsfilter=bereichsfilter)), parameter))
