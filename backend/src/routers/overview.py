"""API für den Einstieg: zuletzt geänderte Seiten und Schlagwortübersicht.

Das ist die Startseite eines Confluence-artigen Wikis — was hat sich getan, und
welche Themen gibt es. Beides ist konsequent auf die lesbaren Bereiche
eingeschränkt.
"""

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..auth import Principal, get_principal, lesbare_space_ids
from ..database import get_db
from ..models import Label, Page, Space, page_label
from ..schemas import LabelCount, PageSummary

router = APIRouter()


def _als_summary(zeilen: list[tuple[Page, Space]]) -> list[PageSummary]:
    return [
        PageSummary(
            id=seite.id,
            title=seite.title,
            slug=seite.slug,
            space_id=space.id,
            space_key=space.key,
            space_name=space.name,
            updated_at=seite.updated_at,
        )
        for seite, space in zeilen
    ]


@router.get("/recent", response_model=list[PageSummary])
def recent_pages(
    limit: int = Query(default=10, ge=1, le=50),
    db: Session = Depends(get_db),
    principal: Principal = Depends(get_principal),
) -> list[PageSummary]:
    """Zuletzt geänderte Seiten, neueste zuerst."""
    abfrage = (
        select(Page, Space)
        .join(Space, Page.space_id == Space.id)
        # id als zweites Kriterium: gleiche Stempel sollen wenigstens stabil
        # und nicht bei jeder Abfrage anders sortieren.
        .order_by(Page.updated_at.desc(), Page.id.desc())
        .limit(limit)
    )
    erlaubt = lesbare_space_ids(principal, db)
    if erlaubt is not None:
        abfrage = abfrage.where(Page.space_id.in_(erlaubt))
    return _als_summary(list(db.execute(abfrage).tuples()))


@router.get("/labels", response_model=list[LabelCount])
def list_labels(
    db: Session = Depends(get_db),
    principal: Principal = Depends(get_principal),
) -> list[LabelCount]:
    """Alle Schlagwörter mit der Zahl der sichtbaren Seiten, häufigste zuerst.

    Schlagwörter ohne sichtbare Seite fallen heraus — sonst verriete die Liste,
    dass es in einem gesperrten Bereich ein Thema gibt.
    """
    abfrage = (
        select(Label.name, func.count(Page.id).label("anzahl"))
        .join(page_label, page_label.c.label_id == Label.id)
        .join(Page, Page.id == page_label.c.page_id)
        .group_by(Label.name)
        .order_by(func.count(Page.id).desc(), Label.name)
    )
    erlaubt = lesbare_space_ids(principal, db)
    if erlaubt is not None:
        abfrage = abfrage.where(Page.space_id.in_(erlaubt))
    return [LabelCount(name=name, anzahl=anzahl) for name, anzahl in db.execute(abfrage)]


@router.get("/labels/{name}/pages", response_model=list[PageSummary])
def pages_by_label(
    name: str,
    db: Session = Depends(get_db),
    principal: Principal = Depends(get_principal),
) -> list[PageSummary]:
    """Alle sichtbaren Seiten mit diesem Schlagwort."""
    abfrage = (
        select(Page, Space)
        .join(Space, Page.space_id == Space.id)
        .join(page_label, page_label.c.page_id == Page.id)
        .join(Label, Label.id == page_label.c.label_id)
        .where(Label.name == name.strip().lower())
        .order_by(Page.title)
    )
    erlaubt = lesbare_space_ids(principal, db)
    if erlaubt is not None:
        abfrage = abfrage.where(Page.space_id.in_(erlaubt))
    return _als_summary(list(db.execute(abfrage).tuples()))
