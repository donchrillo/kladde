"""Modell `space` — ein Bereich bündelt einen Seitenbaum."""

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ..database import Base

if TYPE_CHECKING:
    from .page import Page
    from .space_permission import SpacePermission


class Space(Base):
    """Oberste Gliederungsebene des Wikis (z. B. "IT" oder "Personal").

    Ein Bereich ist entweder offen (`is_private=False`) — dann gilt der übliche
    Weg über Freigaben und den Administrator-Kurzschluss — oder privat. Privat
    heißt hier wörtlich: **nur der Eigentümer**, ohne Ausnahme und auch nicht
    für Administratoren. Freigaben auf einem privaten Bereich sind deshalb
    nicht bloß leer, sondern verboten (siehe `routers/users.py`).
    """

    __tablename__ = "space"

    id: Mapped[int] = mapped_column(primary_key=True)
    # Kurzschlüssel für die URL, z. B. "it" -> /it/seite.
    key: Mapped[str] = mapped_column(unique=True, index=True)
    name: Mapped[str]
    description: Mapped[str | None] = mapped_column(default=None)
    # Gesetzt bei privaten Bereichen; bei offenen Bereichen bewusst leer, damit
    # "Eigentümer" nicht als zweites, halbgares Rechtekonzept missverstanden wird.
    owner_id: Mapped[int | None] = mapped_column(ForeignKey("user.id"), index=True, default=None)
    is_private: Mapped[bool] = mapped_column(default=False)
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())

    pages: Mapped[list["Page"]] = relationship(back_populates="space")
    permissions: Mapped[list["SpacePermission"]] = relationship(
        back_populates="space",
        cascade="all, delete-orphan",
    )
