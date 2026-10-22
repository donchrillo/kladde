"""Modell `page_version` — Versionshistorie einer Seite."""

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ..database import Base

if TYPE_CHECKING:
    from .page import Page


class PageVersion(Base):
    """Ein eingefrorener Stand einer Seite.

    Jede Änderung hängt eine neue Revision an — auch das Anlegen (Revision 1).
    Die Historie enthält damit immer auch den aktuellen Stand.
    """

    __tablename__ = "page_version"
    __table_args__ = (UniqueConstraint("page_id", "revision", name="uq_page_version_revision"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    page_id: Mapped[int] = mapped_column(ForeignKey("page.id"), index=True)
    revision: Mapped[int]
    title: Mapped[str]
    body: Mapped[str]
    # Ohne Auth gibt der Client den Autor optional selbst an.
    author: Mapped[str | None] = mapped_column(default=None)
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())

    page: Mapped["Page"] = relationship(back_populates="versions")
