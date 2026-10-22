"""API für Seiten (`page`) samt Versionshistorie, Schlagwörtern und Verweisen."""

import difflib

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..auth import Principal, get_principal, lesbare_space_ids, pruefe_bereich
from ..database import get_db
from ..links import links_aktualisieren, verweise_umschreiben
from ..models import Label, Page, PageLink, PageVersion, Recht, Space
from ..schemas import (
    DiffZeile,
    LabelsSet,
    PageCreate,
    PageRead,
    PageSummary,
    PageUpdate,
    PageVersionInfo,
    PageVersionRead,
    VersionDiff,
)
from ..search import aus_index_entfernen, indexieren
from ..slug import slugify
from .attachments import dateien_loeschen

router = APIRouter()

# Maximale Verschachtelung. Die Grenze steht bewusst im Backend, damit sie nicht
# nur eine Empfehlung des Frontends ist.
#
# Ursprünglich 3 (Seite -> Unterseite -> Unter-Unterseite). Auf 5 angehoben für
# die Übernahme aus Confluence: dort lagen 54 Seiten tiefer, und sie umzuhängen
# hätte die gewachsene Gliederung zerschnitten. Tiefer als 5 wird ein Wiki
# unnavigierbar; im Seitenbaum hilft das Zuklappen.
MAX_TIEFE = 5


def _tiefe(parent_id: int | None, db: Session) -> int:
    """Ebene, auf der eine Seite unter diesem Elternteil läge (Wurzel = 1)."""
    tiefe = 1
    lauf = db.get(Page, parent_id) if parent_id is not None else None
    while lauf is not None:
        tiefe += 1
        lauf = db.get(Page, lauf.parent_id) if lauf.parent_id is not None else None
    return tiefe


def _teilbaum_hoehe(seite: Page, db: Session) -> int:
    """Wie viele Ebenen der Ast unter dieser Seite umfasst (die Seite selbst = 1)."""
    kinder = list(db.scalars(select(Page).where(Page.parent_id == seite.id)))
    if not kinder:
        return 1
    return 1 + max(_teilbaum_hoehe(kind, db) for kind in kinder)


def _pruefe_tiefe(parent_id: int | None, db: Session, seite: Page | None = None) -> None:
    """Stellt sicher, dass MAX_TIEFE eingehalten wird.

    Beim Verschieben zählt nicht nur die neue Ebene der Seite selbst, sondern
    auch ihre Unterseiten: sie wandern mit und dürfen nicht unter die Grenze
    rutschen.
    """
    hoehe = _teilbaum_hoehe(seite, db) if seite is not None else 1
    if _tiefe(parent_id, db) + hoehe - 1 > MAX_TIEFE:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Maximal {MAX_TIEFE} Ebenen — die Seite bzw. ihre Unterseiten lägen zu tief",
        )


def _teilbaum(seite: Page, db: Session) -> list[Page]:
    """Die Seite und alle Nachfahren, Eltern vor Kindern."""
    ergebnis = [seite]
    i = 0
    while i < len(ergebnis):
        ergebnis.extend(db.scalars(select(Page).where(Page.parent_id == ergebnis[i].id)))
        i += 1
    return ergebnis


def _seite_holen(page_id: int, db: Session) -> Page:
    seite = db.get(Page, page_id)
    if seite is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Seite nicht gefunden")
    return seite


def _freier_slug(space_id: int, wunsch: str, db: Session) -> str:
    """Macht den Slug im Bereich eindeutig, indem bei Kollision -2, -3 … angehängt wird."""
    basis = slugify(wunsch)
    slug = basis
    nummer = 1
    while db.scalar(select(Page).where(Page.space_id == space_id, Page.slug == slug)) is not None:
        nummer += 1
        slug = f"{basis}-{nummer}"
    return slug


def _naechste_position(space_id: int, parent_id: int | None, db: Session) -> int:
    """Hängt die neue Seite hinter ihren Geschwistern an."""
    hoechste = db.scalar(
        select(func.max(Page.position)).where(
            Page.space_id == space_id, Page.parent_id == parent_id
        )
    )
    return 0 if hoechste is None else hoechste + 1


def _einreihen(seite: Page, stelle: int | None, db: Session) -> None:
    """Setzt die Seite an `stelle` unter ihre Geschwister und nummeriert lückenlos neu.

    `stelle` zählt ab 0 und wird auf den gültigen Bereich geklemmt; `None` heißt
    "ans Ende". Ohne das Neunummerieren landeten zwei Seiten auf derselben
    Position und stünden dann nur noch alphabetisch hintereinander.
    """
    geschwister = list(
        db.scalars(
            select(Page)
            .where(
                Page.space_id == seite.space_id,
                Page.parent_id == seite.parent_id,
                Page.id != seite.id,
            )
            .order_by(Page.position, Page.title)
        )
    )
    if stelle is None:
        stelle = len(geschwister)
    geschwister.insert(max(0, min(stelle, len(geschwister))), seite)
    for nummer, eintrag in enumerate(geschwister):
        eintrag.position = nummer


def _autor(principal: Principal, gemeldet: str | None) -> str | None:
    """Wer als Autor in die Revision kommt.

    Mit eingeschalteter Anmeldung gewinnt der angemeldete Benutzer — ein
    Client soll sich keinen fremden Namen ausdenken können. Im offenen Betrieb
    bleibt der mitgeschickte Wert stehen; davon lebt der Confluence-Import, der
    die ursprünglichen Autoren mitbringt.
    """
    if principal.user_id is not None:
        return principal.display_name
    return gemeldet


def _revision_anlegen(seite: Page, author: str | None, db: Session) -> None:
    """Friert den aktuellen Stand der Seite als neue Revision ein."""
    letzte = db.scalar(
        select(func.max(PageVersion.revision)).where(PageVersion.page_id == seite.id)
    )
    db.add(
        PageVersion(
            page_id=seite.id,
            revision=1 if letzte is None else letzte + 1,
            title=seite.title,
            body=seite.body,
            author=author,
        )
    )


def _pruefe_elternteil(
    seite: Page, parent_id: int | None, db: Session, ziel_space_id: int | None = None
) -> None:
    """Verhindert Zyklen: eine Seite darf nicht unter sich selbst hängen.

    `ziel_space_id` weicht beim Bereichswechsel vom Bereich der Seite ab — der
    neue Elternteil muss im Zielbereich liegen, nicht im alten.
    """
    if parent_id is None:
        return
    erwarteter_bereich = ziel_space_id if ziel_space_id is not None else seite.space_id
    if parent_id == seite.id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Eine Seite kann nicht ihre eigene Elternseite sein",
        )
    elternteil = db.get(Page, parent_id)
    if elternteil is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Elternseite nicht gefunden"
        )
    if elternteil.space_id != erwarteter_bereich:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Elternseite liegt in einem anderen Bereich",
        )
    # Aufstieg zur Wurzel: taucht `seite` auf, wäre der Baum zyklisch.
    lauf: Page | None = elternteil
    while lauf is not None:
        if lauf.id == seite.id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Verschieben unter eine eigene Unterseite ist nicht möglich",
            )
        lauf = db.get(Page, lauf.parent_id) if lauf.parent_id is not None else None


@router.post("", response_model=PageRead, status_code=status.HTTP_201_CREATED)
def create_page(
    data: PageCreate,
    db: Session = Depends(get_db),
    principal: Principal = Depends(get_principal),
) -> Page:
    if db.get(Space, data.space_id) is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Bereich nicht gefunden")
    pruefe_bereich(principal, data.space_id, Recht.SCHREIBEN, db)
    if data.parent_id is not None:
        elternteil = db.get(Page, data.parent_id)
        if elternteil is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Elternseite nicht gefunden"
            )
        if elternteil.space_id != data.space_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Elternseite liegt in einem anderen Bereich",
            )
    _pruefe_tiefe(data.parent_id, db)

    seite = Page(
        space_id=data.space_id,
        parent_id=data.parent_id,
        title=data.title,
        slug=_freier_slug(data.space_id, data.slug or data.title, db),
        body=data.body,
        position=_naechste_position(data.space_id, data.parent_id, db),
    )
    db.add(seite)
    db.flush()  # vergibt die id, die die Revision braucht
    _revision_anlegen(seite, _autor(principal, data.author), db)
    indexieren(db, seite)
    links_aktualisieren(seite, db)
    db.commit()
    db.refresh(seite)
    return seite


@router.get("/{page_id}", response_model=PageRead)
def get_page(
    page_id: int,
    db: Session = Depends(get_db),
    principal: Principal = Depends(get_principal),
) -> Page:
    seite = _seite_holen(page_id, db)
    pruefe_bereich(principal, seite.space_id, Recht.LESEN, db)
    return seite


@router.patch("/{page_id}", response_model=PageRead)
def update_page(
    page_id: int,
    data: PageUpdate,
    db: Session = Depends(get_db),
    principal: Principal = Depends(get_principal),
) -> Page:
    seite = _seite_holen(page_id, db)
    pruefe_bereich(principal, seite.space_id, Recht.SCHREIBEN, db)
    felder = data.model_dump(exclude_unset=True)

    wechselt = "space_id" in felder and felder["space_id"] != seite.space_id
    umgehaengt = wechselt
    if wechselt:
        _bereich_wechseln(seite, felder["space_id"], felder.get("parent_id"), db, principal)
    elif "parent_id" in felder:
        umgehaengt = felder["parent_id"] != seite.parent_id
        # Umhängen innerhalb desselben Bereichs bleibt `schreiben`: das ist
        # Gliederungspflege, nicht Wegschaffen. Erst der Bereichswechsel oben
        # verlangt `loeschen` im Quellbereich.
        _pruefe_elternteil(seite, felder["parent_id"], db)
        _pruefe_tiefe(felder["parent_id"], db, seite)
        seite.parent_id = felder["parent_id"]
    if "title" in felder:
        seite.title = felder["title"]
    if "body" in felder:
        seite.body = felder["body"]
    # Wer umgehängt wird, kommt ans Ende der neuen Geschwister — die alte
    # Nummer gehörte zur alten Ebene. Eine mitgeschickte Position gewinnt.
    if "position" in felder:
        _einreihen(seite, felder["position"], db)
    elif umgehaengt:
        _einreihen(seite, None, db)

    # Nur inhaltliche Änderungen sind eine neue Revision wert — Verschieben
    # und Umsortieren ändern den Text nicht.
    if "title" in felder or "body" in felder:
        _revision_anlegen(seite, _autor(principal, data.author), db)
        indexieren(db, seite)
        links_aktualisieren(seite, db)

    db.commit()
    db.refresh(seite)
    return seite


def _bereich_wechseln(
    seite: Page,
    ziel_space_id: int,
    parent_id: int | None,
    db: Session,
    principal: Principal,
) -> None:
    """Verschiebt eine Seite samt Unterseiten in einen anderen Bereich.

    Drei Dinge müssen dabei mitziehen, sonst bleibt ein halb umgezogener Baum
    stehen:

    * **Der ganze Ast.** Bliebe eine Unterseite im alten Bereich, hinge sie an
      einem Elternteil, den es dort nicht mehr gibt.
    * **Die Slugs.** Sie sind pro Bereich eindeutig; im Zielbereich kann
      derselbe schon vergeben sein.
    * **Die Verweise.** Interne Links tragen den Bereichsschlüssel im Text und
      zeigten sonst ins Leere.
    """
    zielbereich = db.get(Space, ziel_space_id)
    if zielbereich is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Bereich nicht gefunden")
    # Aus dem Quellbereich verschwindet die Seite — das ist Wegschaffen und
    # verlangt dort `loeschen`. Im Zielbereich entsteht sie neu: `schreiben`.
    pruefe_bereich(principal, seite.space_id, Recht.LOESCHEN, db)
    pruefe_bereich(principal, ziel_space_id, Recht.SCHREIBEN, db)

    _pruefe_elternteil(seite, parent_id, db, ziel_space_id=ziel_space_id)
    _pruefe_tiefe(parent_id, db, seite)

    ast = _teilbaum(seite, db)
    alter_schluessel = seite.space.key

    # Alte Adressen merken, bevor sie sich ändern.
    aenderungen: dict[int, tuple[str, str]] = {}
    alte_pfade = {s.id: f"/wiki/{alter_schluessel}/{s.slug}" for s in ast}

    for eintrag in ast:
        eintrag.space_id = ziel_space_id
        # Erst nach dem Bereichswechsel nach einem freien Slug fragen: gesucht
        # wird im Zielbereich, und die schon umgezogenen Geschwister zählen mit.
        eintrag.slug = _freier_slug(ziel_space_id, eintrag.slug, db)
        neuer_pfad = f"/wiki/{zielbereich.key}/{eintrag.slug}"
        if neuer_pfad != alte_pfade[eintrag.id]:
            aenderungen[eintrag.id] = (alte_pfade[eintrag.id], neuer_pfad)

    seite.parent_id = parent_id

    # Verweise anderer Seiten (und der verschobenen untereinander) nachziehen —
    # aber nur in Bereichen, die der Verschiebende auch lesen darf. Fremde
    # Privatbereiche bleiben unberührt (siehe `verweise_umschreiben`).
    umzug = f"Umzug nach „{zielbereich.name}“ durch {_autor(principal, None) or 'unbekannt'}"
    for geaendert in verweise_umschreiben(db, aenderungen, lesbare_space_ids(principal, db)):
        # Eine Revision je berührter Seite: sonst ändert sich fremder Text
        # spurlos, und der Autor findet in seiner Historie nichts wieder.
        _revision_anlegen(geaendert, umzug, db)
        indexieren(db, geaendert)


@router.delete("/{page_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_page(
    page_id: int,
    db: Session = Depends(get_db),
    principal: Principal = Depends(get_principal),
) -> None:
    seite = _seite_holen(page_id, db)
    pruefe_bereich(principal, seite.space_id, Recht.LOESCHEN, db)
    kinder = db.scalar(select(func.count()).select_from(Page).where(Page.parent_id == seite.id))
    if kinder:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Seite hat Unterseiten und kann nicht gelöscht werden",
        )
    # Erst die Dateien von der Platte, dann die Zeile: die Anhang-Zeilen
    # verschwinden per Cascade, ihre Dateien nicht.
    dateien_loeschen(list(seite.attachments))
    aus_index_entfernen(db, seite.id)
    db.delete(seite)  # Revisionen und Anhänge hängen per Cascade daran
    db.commit()


@router.get("/{page_id}/versions", response_model=list[PageVersionInfo])
def list_versions(
    page_id: int,
    db: Session = Depends(get_db),
    principal: Principal = Depends(get_principal),
) -> list[PageVersion]:
    seite = _seite_holen(page_id, db)
    pruefe_bereich(principal, seite.space_id, Recht.LESEN, db)
    return list(
        db.scalars(
            select(PageVersion)
            .where(PageVersion.page_id == page_id)
            .order_by(PageVersion.revision.desc())
        )
    )


@router.get("/{page_id}/versions/{revision}", response_model=PageVersionRead)
def get_version(
    page_id: int,
    revision: int,
    db: Session = Depends(get_db),
    principal: Principal = Depends(get_principal),
) -> PageVersion:
    seite = _seite_holen(page_id, db)
    pruefe_bereich(principal, seite.space_id, Recht.LESEN, db)
    version = db.scalar(
        select(PageVersion).where(PageVersion.page_id == page_id, PageVersion.revision == revision)
    )
    if version is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Revision nicht gefunden")
    return version


# ── Revision zurückholen und vergleichen ────────────────────────────────────


@router.post("/{page_id}/versions/{revision}/restore", response_model=PageRead)
def restore_version(
    page_id: int,
    revision: int,
    author: str | None = None,
    db: Session = Depends(get_db),
    principal: Principal = Depends(get_principal),
) -> Page:
    """Holt einen alten Stand zurück.

    Der alte Inhalt wird als *neue* Revision obendrauf gelegt, statt die
    Historie abzuschneiden — so bleibt nachvollziehbar, dass zurückgeholt wurde,
    und der Schritt lässt sich selbst wieder rückgängig machen.
    """
    seite = _seite_holen(page_id, db)
    pruefe_bereich(principal, seite.space_id, Recht.SCHREIBEN, db)

    alt = db.scalar(
        select(PageVersion).where(PageVersion.page_id == page_id, PageVersion.revision == revision)
    )
    if alt is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Revision nicht gefunden")

    seite.title = alt.title
    seite.body = alt.body
    _revision_anlegen(seite, _autor(principal, author), db)
    indexieren(db, seite)
    links_aktualisieren(seite, db)
    db.commit()
    db.refresh(seite)
    return seite


@router.get("/{page_id}/versions/{revision}/diff", response_model=VersionDiff)
def diff_version(
    page_id: int,
    revision: int,
    gegen: int = Query(..., description="Revision, gegen die verglichen wird"),
    db: Session = Depends(get_db),
    principal: Principal = Depends(get_principal),
) -> VersionDiff:
    """Zeilenweiser Vergleich zweier Revisionen.

    Serverseitig mit `difflib`, damit das Frontend keine Diff-Bibliothek braucht.
    Die ältere Revision ist immer die linke Seite, unabhängig von der Reihenfolge
    in der Anfrage.
    """
    seite = _seite_holen(page_id, db)
    pruefe_bereich(principal, seite.space_id, Recht.LESEN, db)

    von_nr, nach_nr = sorted((revision, gegen))
    staende: dict[int, PageVersion] = {}
    for nummer in (von_nr, nach_nr):
        stand = db.scalar(
            select(PageVersion).where(
                PageVersion.page_id == page_id, PageVersion.revision == nummer
            )
        )
        if stand is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Revision {nummer} nicht gefunden",
            )
        staende[nummer] = stand

    zeilen: list[DiffZeile] = []
    vergleich = difflib.ndiff(
        staende[von_nr].body.splitlines(),
        staende[nach_nr].body.splitlines(),
    )
    for eintrag in vergleich:
        marke, text = eintrag[:2], eintrag[2:]
        if marke == "  ":
            zeilen.append(DiffZeile(art="gleich", text=text))
        elif marke == "+ ":
            zeilen.append(DiffZeile(art="plus", text=text))
        elif marke == "- ":
            zeilen.append(DiffZeile(art="minus", text=text))
        # "? " markiert Zeichenpositionen und ist für die Anzeige unbrauchbar.

    return VersionDiff(von_revision=von_nr, nach_revision=nach_nr, zeilen=zeilen)


# ── Schlagwörter ────────────────────────────────────────────────────────────


def _label_holen(name: str, db: Session) -> Label:
    """Vorhandenes Schlagwort oder ein neues; Namen werden normalisiert."""
    sauber = name.strip().lower()
    vorhanden = db.scalar(select(Label).where(Label.name == sauber))
    if vorhanden is not None:
        return vorhanden
    neu = Label(name=sauber)
    db.add(neu)
    db.flush()
    return neu


@router.put("/{page_id}/labels", response_model=PageRead)
def set_labels(
    page_id: int,
    data: LabelsSet,
    db: Session = Depends(get_db),
    principal: Principal = Depends(get_principal),
) -> Page:
    """Ersetzt die Schlagwörter der Seite vollständig."""
    seite = _seite_holen(page_id, db)
    pruefe_bereich(principal, seite.space_id, Recht.SCHREIBEN, db)

    namen = {n.strip().lower() for n in data.names if n.strip()}
    seite.labels = [_label_holen(name, db) for name in sorted(namen)]
    db.commit()
    db.refresh(seite)
    return seite


# ── Rückverweise ────────────────────────────────────────────────────────────


def _zusammenfassung(zeilen: list[tuple[Page, Space]]) -> list[PageSummary]:
    return [
        PageSummary(
            id=seite.id,
            title=seite.title,
            slug=seite.slug,
            space_id=space.id,
            space_key=space.key,
            space_name=space.name,
            updated_at=seite.updated_at,
        )
        for seite, space in zeilen
    ]


@router.get("/{page_id}/backlinks", response_model=list[PageSummary])
def list_backlinks(
    page_id: int,
    db: Session = Depends(get_db),
    principal: Principal = Depends(get_principal),
) -> list[PageSummary]:
    """Seiten, die auf diese Seite verweisen — nur aus lesbaren Bereichen."""
    seite = _seite_holen(page_id, db)
    pruefe_bereich(principal, seite.space_id, Recht.LESEN, db)

    abfrage = (
        select(Page, Space)
        .join(PageLink, PageLink.source_page_id == Page.id)
        .join(Space, Page.space_id == Space.id)
        .where(PageLink.target_page_id == page_id)
        .order_by(Page.title)
    )
    erlaubt = lesbare_space_ids(principal, db)
    if erlaubt is not None:
        abfrage = abfrage.where(Page.space_id.in_(erlaubt))
    return _zusammenfassung(list(db.execute(abfrage).tuples()))
