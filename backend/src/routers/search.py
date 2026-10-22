"""API für die Volltextsuche.

`GET /api/search?q=…` durchsucht Titel und Inhalt aller Seiten, auf die der
Anfragende Lesezugriff hat. Die Bereichseinschränkung passiert in der Abfrage
selbst, nicht erst beim Filtern des Ergebnisses — ein Treffer aus einem
gesperrten Bereich soll gar nicht erst entstehen.
"""

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..auth import Principal, get_principal, lesbare_space_ids
from ..database import get_db
from ..models import Page, Space
from ..schemas import SearchHit
from ..search import ist_fts_verfuegbar, suche_fts, suche_like

router = APIRouter()


@router.get("", response_model=list[SearchHit])
def search(
    q: str = Query(default="", description="Suchbegriff"),
    limit: int = Query(default=30, ge=1, le=100),
    space_id: int | None = Query(default=None, description="Nur in diesem Bereich suchen"),
    db: Session = Depends(get_db),
    principal: Principal = Depends(get_principal),
) -> list[SearchHit]:
    if not q.strip():
        return []

    erlaubt = lesbare_space_ids(principal, db)
    if space_id is not None:
        # Der Filter darf nur einschränken, nie Rechte erweitern.
        erlaubt = [space_id] if erlaubt is None else [s for s in erlaubt if s == space_id]
    zeilen = (
        suche_fts(db, q, erlaubt, limit)
        if ist_fts_verfuegbar(db)
        else suche_like(db, q, erlaubt, limit)
    )
    if not zeilen:
        return []

    # Titel und Bereich in einem Rutsch nachladen, statt je Treffer einzeln.
    ausschnitte = {zeile.page_id: zeile.ausschnitt for zeile in zeilen}
    seiten = {
        seite.id: (seite, space)
        for seite, space in db.execute(
            select(Page, Space)
            .join(Space, Page.space_id == Space.id)
            .where(Page.id.in_(list(ausschnitte)))
        )
    }

    treffer: list[SearchHit] = []
    for zeile in zeilen:  # Reihenfolge der Suche (Relevanz) beibehalten
        eintrag = seiten.get(zeile.page_id)
        if eintrag is None:
            continue
        seite, space = eintrag
        treffer.append(
            SearchHit(
                page_id=seite.id,
                title=seite.title,
                slug=seite.slug,
                space_id=space.id,
                space_key=space.key,
                space_name=space.name,
                excerpt=ausschnitte[zeile.page_id] or "",
            )
        )
    return treffer
