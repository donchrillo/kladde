"""Modell `page` — eine Wiki-Seite, hierarchisch über `parent_id` verschachtelt."""

from datetime import UTC, datetime
from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ..database import Base

if TYPE_CHECKING:
    from .attachment import Attachment
    from .label import Label
    from .page_link import PageLink
    from .page_version import PageVersion
    from .space import Space


def _jetzt() -> datetime:
    """UTC ohne Zeitzonenangabe, aber mit Mikrosekunden.

    `CURRENT_TIMESTAMP` von SQLite löst nur auf Sekunden auf — mehrere
    Änderungen in derselben Sekunde bekämen denselben Stempel, und die Liste
    „zuletzt geändert" sortierte dann willkürlich. Zeitzonenlos, damit die Werte
    zum bestehenden `server_default` passen und die Textsortierung in SQLite
    weiter stimmt.
    """
    return datetime.now(UTC).replace(tzinfo=None)


class Page(Base):
    """Eine Seite mit Markdown-Inhalt.

    Der Slug ist pro Bereich eindeutig — unabhängig von der Position im Baum.
    Das hält Links stabil, wenn eine Seite verschoben wird.
    """

    __tablename__ = "page"
    __table_args__ = (UniqueConstraint("space_id", "slug", name="uq_page_space_slug"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    space_id: Mapped[int] = mapped_column(ForeignKey("space.id"), index=True)
    parent_id: Mapped[int | None] = mapped_column(ForeignKey("page.id"), default=None, index=True)
    title: Mapped[str]
    slug: Mapped[str] = mapped_column(index=True)
    body: Mapped[str] = mapped_column(default="")
    # Sortierung unter Geschwistern; kleinere Werte zuerst.
    position: Mapped[int] = mapped_column(default=0)
    created_at: Mapped[datetime] = mapped_column(default=_jetzt, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        default=_jetzt, onupdate=_jetzt, server_default=func.now()
    )

    space: Mapped["Space"] = relationship(back_populates="pages")
    children: Mapped[list["Page"]] = relationship(
        back_populates="parent",
        order_by="(Page.position, Page.title)",
    )
    parent: Mapped["Page | None"] = relationship(back_populates="children", remote_side=[id])
    versions: Mapped[list["PageVersion"]] = relationship(
        back_populates="page",
        cascade="all, delete-orphan",
        order_by="PageVersion.revision",
    )
    attachments: Mapped[list["Attachment"]] = relationship(
        back_populates="page",
        cascade="all, delete-orphan",
        order_by="Attachment.created_at",
    )
    labels: Mapped[list["Label"]] = relationship(
        secondary="page_label",
        back_populates="pages",
        order_by="Label.name",
    )
    # Verweise dieser Seite auf andere ...
    ausgehende_links: Mapped[list["PageLink"]] = relationship(
        foreign_keys="PageLink.source_page_id",
        back_populates="source",
        cascade="all, delete-orphan",
    )
    # ... und Verweise anderer Seiten hierher.
    eingehende_links: Mapped[list["PageLink"]] = relationship(
        foreign_keys="PageLink.target_page_id",
        back_populates="target",
        cascade="all, delete-orphan",
    )
