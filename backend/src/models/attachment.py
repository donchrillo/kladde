"""Modell `attachment` — eine Datei, die an einer Seite hängt.

Die Datei selbst liegt im Dateisystem (`ATTACHMENT_DIR`), nicht in der Datenbank:
das hält die DB klein, macht Backups unabhängig voneinander und erlaubt später
das Ausliefern durch Caddy. In der Tabelle steht nur der Verweis.
"""

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ..database import Base

if TYPE_CHECKING:
    from .page import Page


class Attachment(Base):
    """Metadaten einer hochgeladenen Datei."""

    __tablename__ = "attachment"

    id: Mapped[int] = mapped_column(primary_key=True)
    page_id: Mapped[int] = mapped_column(ForeignKey("page.id"), index=True)
    # Anzeigename, wie der Benutzer die Datei hochgeladen hat.
    filename: Mapped[str]
    # Name auf der Platte: eine UUID ohne Bezug zum Originalnamen. Damit kann ein
    # praeparierter Dateiname weder Pfade verlassen noch andere Dateien ueberschreiben.
    stored_name: Mapped[str] = mapped_column(unique=True)
    content_type: Mapped[str] = mapped_column(default="application/octet-stream")
    size_bytes: Mapped[int] = mapped_column(default=0)
    uploaded_by: Mapped[str | None] = mapped_column(default=None)
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())

    page: Mapped["Page"] = relationship(back_populates="attachments")
