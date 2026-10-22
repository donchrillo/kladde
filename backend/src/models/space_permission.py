"""Modell `space_permission` — wer darf was in welchem Bereich.

Rechte hängen bewusst am Bereich, nicht an der einzelnen Seite. Das ist das
Modell von Confluence und passt zum geplanten Einsatz: ein Bereich
"Geschäftsleitung" wird für einzelne Personen freigeschaltet, ein Bereich
"Lager" für alle. Seitenweise Ausnahmen gäbe es damit nicht — sie sind in der
Praxis auch die Hauptquelle für versehentlich offene Inhalte.
"""

import enum
from typing import TYPE_CHECKING

from sqlalchemy import Enum, ForeignKey, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ..database import Base

if TYPE_CHECKING:
    from .space import Space
    from .user import User


class Recht(enum.StrEnum):
    """Zugriffsstufen, aufsteigend. Jede Stufe schließt die darunter ein."""

    LESEN = "lesen"
    SCHREIBEN = "schreiben"
    # Wegwerfen ist etwas anderes als pflegen: wer Seiten schreibt, soll sie
    # nicht zwangsläufig löschen oder in einen anderen Bereich schaffen können.
    LOESCHEN = "loeschen"
    VERWALTEN = "verwalten"


# Rangfolge für den Vergleich "reicht das vorhandene Recht für die Anforderung?".
RANG: dict[Recht, int] = {
    Recht.LESEN: 1,
    Recht.SCHREIBEN: 2,
    Recht.LOESCHEN: 3,
    Recht.VERWALTEN: 4,
}


class SpacePermission(Base):
    """Freigabe eines Bereichs für einen Benutzer."""

    __tablename__ = "space_permission"
    __table_args__ = (
        UniqueConstraint("space_id", "user_id", name="uq_space_permission_space_user"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    space_id: Mapped[int] = mapped_column(ForeignKey("space.id"), index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("user.id"), index=True)
    level: Mapped[Recht] = mapped_column(Enum(Recht, native_enum=False), default=Recht.LESEN)

    space: Mapped["Space"] = relationship(back_populates="permissions")
    user: Mapped["User"] = relationship(back_populates="permissions")
