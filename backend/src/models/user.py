"""Modell `user` — Benutzerkonto.

Angelegt schon jetzt, obwohl die Anmeldung noch aus ist (`AUTH_ENABLED=false`).
Grund: Rechte nachträglich in ein gefülltes Wiki einzuziehen bedeutet, jede
Route und jeden Bestandsinhalt anzufassen. Das Fundament steht daher von Anfang
an, und der Login wird später nur noch eingeschaltet.
"""

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ..database import Base

if TYPE_CHECKING:
    from .space_permission import SpacePermission
    from .user_session import UserSession


class User(Base):
    """Ein Mensch, der das Wiki benutzt."""

    __tablename__ = "user"

    id: Mapped[int] = mapped_column(primary_key=True)
    username: Mapped[str] = mapped_column(unique=True, index=True)
    display_name: Mapped[str]
    # Noch leer, solange die Anmeldung aus ist. Später ein Hash, nie das Klartext-Passwort.
    password_hash: Mapped[str | None] = mapped_column(default=None)
    # Administratoren sehen und bearbeiten alle Bereiche, ohne Einzelfreigabe.
    is_admin: Mapped[bool] = mapped_column(default=False)
    is_active: Mapped[bool] = mapped_column(default=True)
    # Einen Bereich anzulegen ist keine Aktion *in* einem Bereich — es gibt also
    # kein Bereichsrecht, an dem das hängen könnte. Deshalb ein Flag am Konto.
    darf_bereiche_anlegen: Mapped[bool] = mapped_column(default=False)
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())

    permissions: Mapped[list["SpacePermission"]] = relationship(
        back_populates="user",
        cascade="all, delete-orphan",
    )
    # Konto löschen oder deaktivieren beendet damit auch alle offenen Sitzungen.
    sessions: Mapped[list["UserSession"]] = relationship(
        back_populates="user",
        cascade="all, delete-orphan",
    )
