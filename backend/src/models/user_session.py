"""Modell `user_session` — eine angemeldete Sitzung.

Sitzungen liegen bewusst in der Datenbank statt in einem JWT: nur so lässt sich
eine Anmeldung wirklich beenden (Abmelden, Passwortwechsel, Konto deaktiviert).
Der Preis ist ein Datenbankzugriff je Anfrage — bei einem internen Wiki mit
SQLite auf derselben Maschine irrelevant.

Gespeichert wird nie das Token selbst, sondern nur sein SHA-256. Wer die
Datenbankdatei liest, kann damit keine fremde Sitzung übernehmen.

Der Klassenname lautet `UserSession` (nicht `Session`), weil in fast jeder
Backend-Datei bereits `sqlalchemy.orm.Session` importiert ist.
"""

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ..database import Base

if TYPE_CHECKING:
    from .user import User


class UserSession(Base):
    """Eine gültige Anmeldung, adressiert über den Hash ihres Tokens."""

    __tablename__ = "user_session"

    id: Mapped[int] = mapped_column(primary_key=True)
    token_hash: Mapped[str] = mapped_column(unique=True, index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("user.id", ondelete="CASCADE"), index=True)
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())
    # Rollierend: verlängert sich, solange die Sitzung benutzt wird.
    expires_at: Mapped[datetime] = mapped_column(index=True)

    user: Mapped["User"] = relationship(back_populates="sessions")
