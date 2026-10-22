"""Pydantic-Schemas (von den ORM-Modellen entkoppelt)."""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator

from .models import Recht

# ── Bereiche ────────────────────────────────────────────────────────────────


class SpaceCreate(BaseModel):
    """Eingabe beim Anlegen eines Bereichs."""

    name: str = Field(min_length=1)
    # Ohne Angabe wird der Schlüssel aus dem Namen abgeleitet.
    key: str | None = None
    description: str | None = None


class SpaceUpdate(BaseModel):
    """Änderung an einem Bereich; nicht gesetzte Felder bleiben unberührt.

    Bewusst schmal: Ein privater Bereich lässt sich **nicht** an ein anderes
    Konto übertragen. Das gab es einmal als Administratoreingriff — damit war
    die Zusage „privat ist privat" aber gebrochen, denn wer übertragen darf,
    kann sich selbst zum Eigentümer machen und hineinsehen. Ein Administrator
    sieht einen fremden Privatbereich nur als Metadaten-Zeile und darf ihn
    löschen, solange er leer ist; alles andere macht `tools/bereich_entfernen.py`,
    ohne den Inhalt zu zeigen.

    Der Schlüssel bleibt ebenfalls außen vor, damit bestehende Links halten.
    """

    name: str | None = Field(default=None, min_length=1)
    description: str | None = None


class SpaceRead(BaseModel):
    """Ausgabe-Repräsentation eines Bereichs."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    key: str
    name: str
    description: str | None
    owner_id: int | None
    is_private: bool
    created_at: datetime
    # Das eigene Recht in diesem Bereich, damit die Oberfläche nur anbietet,
    # was auch durchgeht. `None` heißt "kein Recht" und kommt nur in der
    # Verwaltungsliste vor (fremder Privatbereich). Die Prüfung bleibt
    # selbstverständlich serverseitig — das hier ist eine Anzeigehilfe.
    mein_recht: Recht | None = None


class SpaceAdminRead(SpaceRead):
    """Bereichsliste für die Verwaltung — Metadaten, niemals Inhalt.

    Der Administrator sieht damit auch die privaten Bereiche als Zeile: Name,
    Eigentümer, Seitenzahl. Alles darüber hinaus bleibt ihm verschlossen.
    """

    owner_name: str | None
    seiten: int


# ── Seiten ──────────────────────────────────────────────────────────────────


class PageCreate(BaseModel):
    """Eingabe beim Anlegen einer Seite."""

    space_id: int
    title: str = Field(min_length=1)
    parent_id: int | None = None
    slug: str | None = None
    body: str = ""
    author: str | None = None


class PageUpdate(BaseModel):
    """Teil-Aktualisierung einer Seite; nicht gesetzte Felder bleiben unberührt."""

    title: str | None = Field(default=None, min_length=1)
    body: str | None = None
    parent_id: int | None = None
    # Bereichswechsel: nimmt den ganzen Ast mit, vergibt im Zielbereich freie
    # Slugs und schreibt die internen Verweise um.
    space_id: int | None = None
    # Stelle unter den Geschwistern, ab 0; die übrigen rücken nach und werden
    # lückenlos neu nummeriert. `null` setzt die Seite ans Ende.
    position: int | None = None
    author: str | None = None


class PageRead(BaseModel):
    """Vollständige Seite inklusive Markdown-Inhalt."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    space_id: int
    parent_id: int | None
    title: str
    slug: str
    body: str
    position: int
    created_at: datetime
    updated_at: datetime
    labels: list[str] = []

    @field_validator("labels", mode="before")
    @classmethod
    def _nur_namen(cls, wert: object) -> list[str]:
        """Aus den Label-Objekten des ORM die reinen Namen machen."""
        if not isinstance(wert, list):
            return []
        return [eintrag.name if hasattr(eintrag, "name") else str(eintrag) for eintrag in wert]


class PageNode(BaseModel):
    """Knoten im Seitenbaum — ohne `body`, damit der Baum schlank bleibt."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    parent_id: int | None
    title: str
    slug: str
    position: int
    children: list["PageNode"] = []


# ── Versionen ───────────────────────────────────────────────────────────────


class PageVersionRead(BaseModel):
    """Ein Stand aus der Versionshistorie."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    page_id: int
    revision: int
    title: str
    body: str
    author: str | None
    created_at: datetime


class PageVersionInfo(BaseModel):
    """Kopfdaten einer Revision für die Versionsliste (ohne `body`)."""

    model_config = ConfigDict(from_attributes=True)

    revision: int
    title: str
    author: str | None
    created_at: datetime


# ── Anhänge ─────────────────────────────────────────────────────────────────


class AttachmentRead(BaseModel):
    """Metadaten eines Anhangs; der Download läuft über `/api/attachments/{id}`."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    page_id: int
    filename: str
    content_type: str
    size_bytes: int
    uploaded_by: str | None
    created_at: datetime


# ── Suche ───────────────────────────────────────────────────────────────────


class SearchHit(BaseModel):
    """Ein Suchtreffer mit genug Kontext, um ihn in der Liste einzuordnen."""

    page_id: int
    title: str
    slug: str
    space_id: int
    space_key: str
    space_name: str
    # Textausschnitt um den Treffer; Fundstellen mit [[ ]] markiert.
    excerpt: str


# ── Benutzer und Rechte ─────────────────────────────────────────────────────


class UserCreate(BaseModel):
    """Eingabe beim Anlegen eines Benutzers."""

    username: str = Field(min_length=1)
    display_name: str = Field(min_length=1)
    is_admin: bool = False
    darf_bereiche_anlegen: bool = False
    # Startpasswort. Acht Zeichen als untere Schranke; die Konten legt ein
    # Administrator an, eine Passwortrichtlinie wäre hier Theater.
    password: str = Field(min_length=8)


class UserUpdate(BaseModel):
    """Änderung an einem Konto. Alles optional — nur Gesetztes wird übernommen."""

    display_name: str | None = Field(default=None, min_length=1)
    is_admin: bool | None = None
    is_active: bool | None = None
    darf_bereiche_anlegen: bool | None = None


class PasswordSet(BaseModel):
    """Passwort ändern.

    Administratoren dürfen `altes_passwort` weglassen (Zurücksetzen); wer sein
    eigenes ändert, muss es angeben.
    """

    altes_passwort: str | None = None
    neues_passwort: str = Field(min_length=8)


class LoginRequest(BaseModel):
    username: str = Field(min_length=1)
    password: str = Field(min_length=1)


class MeRead(BaseModel):
    """Wer gerade angemeldet ist — Antwort von /api/auth/login und /me.

    `ist_offener_betrieb` sagt dem Frontend, dass gar keine Anmeldung aktiv ist
    (`AUTH_ENABLED=false`); dann bleiben Abmelden und Verwaltung verborgen.
    """

    id: int | None
    username: str
    display_name: str
    is_admin: bool
    darf_bereiche_anlegen: bool
    ist_offener_betrieb: bool


class UserRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    username: str
    display_name: str
    is_admin: bool
    is_active: bool
    darf_bereiche_anlegen: bool
    created_at: datetime


class PermissionSet(BaseModel):
    """Freigabe eines Bereichs für einen Benutzer setzen."""

    user_id: int
    level: Recht = Recht.LESEN


class PermissionRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    space_id: int
    user_id: int
    level: Recht


# ── Schlagwörter ────────────────────────────────────────────────────────────


class LabelRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str


class LabelCount(BaseModel):
    """Schlagwort mit der Anzahl sichtbarer Seiten — für die Schlagwortliste."""

    name: str
    anzahl: int


class LabelsSet(BaseModel):
    """Schlagwörter einer Seite komplett ersetzen."""

    names: list[str]


# ── Übersicht und Verweise ──────────────────────────────────────────────────


class PageSummary(BaseModel):
    """Kurzform einer Seite für Listen (zuletzt geändert, Rückverweise, Schlagwort)."""

    id: int
    title: str
    slug: str
    space_id: int
    space_key: str
    space_name: str
    updated_at: datetime


# ── Versionsvergleich ───────────────────────────────────────────────────────


class DiffZeile(BaseModel):
    """Eine Zeile im Vergleich zweier Revisionen."""

    # "gleich", "plus" (nur in der neueren) oder "minus" (nur in der älteren)
    art: str
    text: str


class VersionDiff(BaseModel):
    von_revision: int
    nach_revision: int
    zeilen: list[DiffZeile]
