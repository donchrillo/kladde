"""Modell `page_link` — welche Seite verweist auf welche.

Wird bei jedem Speichern aus dem Markdown neu abgeleitet (siehe
`src/links.py`). Eine eigene Tabelle statt einer Auswertung zur Laufzeit, weil
die Frage „wer verlinkt hierher?" sonst jedes Mal alle Seitentexte durchsuchen
müsste.
"""

from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ..database import Base

if TYPE_CHECKING:
    from .page import Page


class PageLink(Base):
    """Ein Verweis von `source_page_id` auf `target_page_id`."""

    __tablename__ = "page_link"
    __table_args__ = (UniqueConstraint("source_page_id", "target_page_id", name="uq_page_link"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    source_page_id: Mapped[int] = mapped_column(
        ForeignKey("page.id", ondelete="CASCADE"), index=True
    )
    target_page_id: Mapped[int] = mapped_column(
        ForeignKey("page.id", ondelete="CASCADE"), index=True
    )

    source: Mapped["Page"] = relationship(
        foreign_keys=[source_page_id], back_populates="ausgehende_links"
    )
    target: Mapped["Page"] = relationship(
        foreign_keys=[target_page_id], back_populates="eingehende_links"
    )
