"""Modelle `label` und `page_label` — freie Schlagwörter an Seiten.

Schlagwörter sind bereichsübergreifend: „drucker" meint dasselbe, ob es im
Bereich IT oder Büro vergeben wurde. Beim Auflisten wird trotzdem auf die
lesbaren Bereiche eingeschränkt, damit ein Schlagwort keine Titel aus einem
gesperrten Bereich verrät.
"""

from typing import TYPE_CHECKING

from sqlalchemy import Column, ForeignKey, Table
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ..database import Base

if TYPE_CHECKING:
    from .page import Page

# Reine Verknüpfungstabelle — sie trägt keine eigenen Daten und braucht daher
# keine ORM-Klasse.
page_label = Table(
    "page_label",
    Base.metadata,
    Column("page_id", ForeignKey("page.id", ondelete="CASCADE"), primary_key=True),
    Column("label_id", ForeignKey("label.id", ondelete="CASCADE"), primary_key=True),
)


class Label(Base):
    """Ein Schlagwort. Der Name ist normalisiert (klein, ohne Randleerzeichen)."""

    __tablename__ = "label"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(unique=True, index=True)

    pages: Mapped[list["Page"]] = relationship(
        secondary=page_label,
        back_populates="labels",
    )
