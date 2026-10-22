"""API für Bereiche (`space`) samt Seitenbaum."""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..auth import (
    Principal,
    get_principal,
    nur_admin,
    pruefe_bereich,
    recht_im_bereich,
    rechte_je_bereich,
    sichtbare_bereiche,
)
from ..database import get_db
from ..models import Page, Recht, Space, SpacePermission, User
from ..schemas import PageNode, SpaceAdminRead, SpaceCreate, SpaceRead, SpaceUpdate
from ..slug import slugify

router = APIRouter()

# Schlüssel, die das Frontend als eigene Routen belegt (`lib/route.ts`) — ein
# Bereich mit diesem Schlüssel wäre über die Oberfläche nie erreichbar.
RESERVIERTE_SCHLUESSEL = frozenset({"verwaltung", "schlagwort", "konto"})


def freier_space_key(wunsch: str, db: Session) -> str:
    """Macht aus einem Namen einen noch freien Bereichsschlüssel.

    Zwei Kollegen dürfen gleich heißen; ihre Privatbereiche brauchen trotzdem
    unterscheidbare URLs.
    """
    basis = slugify(wunsch)
    if basis in RESERVIERTE_SCHLUESSEL:
        basis = f"{basis}-bereich"
    key, zaehler = basis, 2
    while db.scalar(select(Space).where(Space.key == key)) is not None:
        key = f"{basis}-{zaehler}"
        zaehler += 1
    return key


def _mit_recht(space: Space, principal: Principal, db: Session) -> SpaceRead:
    """Ein Bereich für die Ausgabe, ergänzt um das eigene Recht darin."""
    return SpaceRead(
        **SpaceRead.model_validate(space).model_dump(exclude={"mein_recht"}),
        mein_recht=recht_im_bereich(principal, space.id, db),
    )


def _baum(seiten: list[Page]) -> list[PageNode]:
    """Baut aus einer flachen Seitenliste den verschachtelten Baum.

    Bewusst in Python statt per rekursivem SQL: ein Bereich hat überschaubar
    viele Seiten, und so bleibt es auf SQLite wie PostgreSQL identisch.
    """
    knoten = {s.id: PageNode.model_validate(s) for s in seiten}
    for knoten_obj in knoten.values():
        knoten_obj.children = []

    wurzeln: list[PageNode] = []
    for seite in seiten:
        eigener = knoten[seite.id]
        elternteil = knoten.get(seite.parent_id) if seite.parent_id is not None else None
        if elternteil is None:
            wurzeln.append(eigener)
        else:
            elternteil.children.append(eigener)
    return wurzeln


@router.get("", response_model=list[SpaceRead])
def list_spaces(
    db: Session = Depends(get_db),
    principal: Principal = Depends(get_principal),
) -> list[SpaceRead]:
    """Nur die Bereiche, die der Anfragende lesen darf — je mit seinem Recht."""
    bereiche = sichtbare_bereiche(principal, db)
    rechte = rechte_je_bereich(principal, bereiche, db)
    return [
        SpaceRead(
            **SpaceRead.model_validate(space).model_dump(exclude={"mein_recht"}),
            mein_recht=rechte[space.id],
        )
        for space in bereiche
    ]


@router.get("/verwaltung", response_model=list[SpaceAdminRead])
def list_spaces_verwaltung(
    db: Session = Depends(get_db),
    principal: Principal = Depends(nur_admin),
) -> list[SpaceAdminRead]:
    """Alle Bereiche für die Verwaltung — auch die privaten, aber nur als Zeile.

    Muss vor `GET /{key}` stehen, sonst schluckt die Platzhalterroute den Pfad.
    Ausgegeben werden ausschließlich Metadaten; an den Inhalt eines fremden
    privaten Bereichs kommt auch über diese Route niemand.
    """
    seiten_je_space: dict[int, int] = {
        space_id: anzahl
        for space_id, anzahl in db.execute(
            select(Page.space_id, func.count()).group_by(Page.space_id)
        )
    }
    namen: dict[int, str] = {
        user_id: name for user_id, name in db.execute(select(User.id, User.display_name))
    }
    alle = list(db.scalars(select(Space).order_by(Space.name)))
    rechte = rechte_je_bereich(principal, alle, db)
    return [
        SpaceAdminRead(
            **SpaceRead.model_validate(space).model_dump(exclude={"mein_recht"}),
            mein_recht=rechte[space.id],
            owner_name=namen.get(space.owner_id) if space.owner_id is not None else None,
            seiten=seiten_je_space.get(space.id, 0),
        )
        for space in alle
    ]


@router.post("", response_model=SpaceRead, status_code=status.HTTP_201_CREATED)
def create_space(
    data: SpaceCreate,
    db: Session = Depends(get_db),
    principal: Principal = Depends(get_principal),
) -> SpaceRead:
    # Einen Bereich anzulegen ist keine Aktion *in* einem Bereich — es hängt
    # deshalb am Konto, nicht an einem Bereichsrecht.
    if not (principal.is_admin or principal.darf_bereiche_anlegen):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Dieses Konto darf keine Bereiche anlegen",
        )
    key = slugify(data.key or data.name)
    if key in RESERVIERTE_SCHLUESSEL:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"'{key}' ist als Schlüssel reserviert — bitte einen anderen Namen wählen",
        )
    if db.scalar(select(Space).where(Space.key == key)) is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Bereich mit Schlüssel '{key}' existiert bereits",
        )
    space = Space(key=key, name=data.name, description=data.description)
    db.add(space)
    db.flush()
    if not principal.is_admin and principal.user_id is not None:
        # Sonst legte jemand einen Bereich an, den er selbst nicht sieht:
        # Nicht-Administratoren kommen nur über Freigaben an Bereiche heran.
        #
        # Achtung, offene Kante: Freigeben darf seit der Beschränkung in
        # `routers/users.py` nur noch ein Administrator. Ein Nicht-Administrator
        # mit `darf_bereiche_anlegen` sitzt hier also in einem Bereich, den außer
        # ihm niemand sieht und in den er selbst niemanden lassen kann — bis ein
        # Administrator die erste Freigabe einträgt. Solange nur Administratoren
        # Bereiche anlegen dürfen, tritt der Fall nicht ein; wenn er eintreten
        # soll, gehört die Oberfläche für Bereichsverantwortliche gebaut.
        db.add(SpacePermission(space_id=space.id, user_id=principal.user_id, level=Recht.VERWALTEN))
    db.commit()
    db.refresh(space)
    return _mit_recht(space, principal, db)


def _space_oder_404(key: str, db: Session) -> Space:
    space = db.scalar(select(Space).where(Space.key == key))
    if space is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Bereich nicht gefunden")
    return space


@router.get("/{key}", response_model=SpaceRead)
def get_space(
    key: str,
    db: Session = Depends(get_db),
    principal: Principal = Depends(get_principal),
) -> SpaceRead:
    space = _space_oder_404(key, db)
    pruefe_bereich(principal, space.id, Recht.LESEN, db)
    return _mit_recht(space, principal, db)


@router.patch("/{key}", response_model=SpaceRead)
def update_space(
    key: str,
    data: SpaceUpdate,
    db: Session = Depends(get_db),
    principal: Principal = Depends(get_principal),
) -> SpaceRead:
    """Name und Beschreibung ändern. Der Schlüssel bleibt, damit Links halten.

    Nur die tatsächlich mitgeschickten Felder werden angefasst (`exclude_unset`):
    ein PATCH mit ausschließlich `name` löschte sonst die Beschreibung.

    Einen privaten Bereich an ein anderes Konto zu übertragen, gibt es hier
    nicht mehr — siehe `SpaceUpdate`.
    """
    space = _space_oder_404(key, db)
    pruefe_bereich(principal, space.id, Recht.VERWALTEN, db)
    for feld, wert in data.model_dump(exclude_unset=True).items():
        setattr(space, feld, wert)
    db.commit()
    db.refresh(space)
    return _mit_recht(space, principal, db)


@router.delete("/{key}", status_code=status.HTTP_204_NO_CONTENT)
def delete_space(
    key: str,
    db: Session = Depends(get_db),
    principal: Principal = Depends(get_principal),
) -> None:
    """Bereich löschen — nur wenn er leer ist.

    Bewusst kein Abräumen des ganzen Bereichs auf einen Klick: dieselbe Regel
    gilt schon für eine Seite mit Unterseiten. Wer einen Bereich loswerden will,
    räumt ihn vorher aus und sieht dabei, was er wegwirft.

    Ein Administrator darf auch einen fremden privaten Bereich löschen, obwohl
    er ihn nicht lesen kann — für den Fall, dass ein Kollege ausscheidet. Die
    Regel "nur wenn leer" gilt dabei weiter; einen gefüllten Privatbereich
    räumt `tools/bereich_entfernen.py` weg, ohne dass jemand hineinsieht.
    """
    space = _space_oder_404(key, db)
    if not (space.is_private and principal.is_admin):
        pruefe_bereich(principal, space.id, Recht.VERWALTEN, db)
    anzahl = db.scalar(select(func.count()).select_from(Page).where(Page.space_id == space.id))
    if anzahl:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                f"Bereich enthält noch {anzahl} Seite{'' if anzahl == 1 else 'n'} — "
                "diese bitte erst löschen"
            ),
        )
    db.delete(space)  # Freigaben hängen per Cascade daran
    db.commit()


@router.get("/{key}/pages", response_model=list[PageNode])
def get_space_tree(
    key: str,
    db: Session = Depends(get_db),
    principal: Principal = Depends(get_principal),
) -> list[PageNode]:
    """Liefert den Seitenbaum des Bereichs (ohne Seiteninhalte)."""
    space = _space_oder_404(key, db)
    pruefe_bereich(principal, space.id, Recht.LESEN, db)
    seiten = list(
        db.scalars(
            select(Page).where(Page.space_id == space.id).order_by(Page.position, Page.title)
        )
    )
    return _baum(seiten)
