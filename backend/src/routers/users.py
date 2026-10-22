"""API für Benutzer und Bereichsfreigaben.

Alles hier steht ausschließlich Administratoren offen — ohne das könnte sich
mit eingeschalteter Anmeldung jeder selbst ein Administratorkonto anlegen.

Die Freigaberouten prüften früher stattdessen `verwalten` im betroffenen
Bereich: ein Bereichsverantwortlicher sollte seine eigenen Leute freischalten
können, ohne Administrator zu sein. Dazu gibt es aber keine Oberfläche — die
Freigaben liegen ausschließlich unter `#/verwaltung`, und die ist admin-only.
Die Fähigkeit war also nur mit einem selbst gebauten API-Aufruf erreichbar und
verriet dabei über `benutzer_oder_404`, welche Konto-IDs existieren.

Deshalb bis auf Weiteres Administratoren vorbehalten. Die Stufe `verwalten`
bleibt, was sie ist (voller Zugriff im Bereich samt Umbenennen) — sie ist die
Vorbereitung für Bereichsverantwortliche. Wenn die kommen sollen, ist der Weg
zurück kurz: hier wieder `pruefe_bereich(..., VERWALTEN)`, dazu ein schlanker
Endpunkt für die Benutzerauswahl (nur Id und Anzeigename, `GET /api/users`
bleibt admin-only) und `#/verwaltung` für Nicht-Administratoren öffnen,
gefiltert auf die eigenen Bereiche.
"""

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..anmeldeschutz import rechenplatz
from ..auth import (
    COOKIE_NAME,
    Principal,
    benutzer_oder_404,
    get_principal,
    nur_admin,
    sitzungen_beenden,
)
from ..database import get_db
from ..models import Space, SpacePermission, User
from ..passwoerter import hash_erzeugen, hash_pruefen
from ..schemas import (
    PasswordSet,
    PermissionRead,
    PermissionSet,
    UserCreate,
    UserRead,
    UserUpdate,
)
from .spaces import freier_space_key

router = APIRouter()


def _space_holen(space_id: int, db: Session) -> Space:
    space = db.get(Space, space_id)
    if space is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Bereich nicht gefunden")
    return space


@router.get("", response_model=list[UserRead])
def list_users(
    db: Session = Depends(get_db),
    _: Principal = Depends(nur_admin),
) -> list[User]:
    return list(db.scalars(select(User).order_by(User.display_name)))


@router.post("", response_model=UserRead, status_code=status.HTTP_201_CREATED)
def create_user(
    data: UserCreate,
    db: Session = Depends(get_db),
    _: Principal = Depends(nur_admin),
) -> User:
    if db.scalar(select(User).where(User.username == data.username)) is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Benutzer '{data.username}' existiert bereits",
        )
    nutzer = User(
        username=data.username,
        display_name=data.display_name,
        is_admin=data.is_admin,
        darf_bereiche_anlegen=data.darf_bereiche_anlegen,
        password_hash=hash_erzeugen(data.password),
    )
    db.add(nutzer)
    db.flush()
    # Jeder bekommt seinen privaten Bereich — den Platz, an dem er ohne
    # Freigabe und ohne Mitleser arbeiten kann. Auch der Administrator, der das
    # Konto anlegt, sieht davon nie mehr als den Namen.
    db.add(
        Space(
            key=freier_space_key(nutzer.display_name, db),
            name=nutzer.display_name,
            owner_id=nutzer.id,
            is_private=True,
        )
    )
    db.commit()
    db.refresh(nutzer)
    return nutzer


@router.patch("/{user_id}", response_model=UserRead)
def update_user(
    user_id: int,
    data: UserUpdate,
    db: Session = Depends(get_db),
    principal: Principal = Depends(nur_admin),
) -> User:
    """Anzeigename, Administratorrecht, Sperre und "darf Bereiche anlegen"."""
    nutzer = benutzer_oder_404(user_id, db)
    felder = data.model_dump(exclude_unset=True)
    eigenes = nutzer.id == principal.user_id

    # Dieselben zwei Fallen wie beim Löschen: sich nicht selbst aussperren und
    # nicht den letzten Administrator entmachten.
    if eigenes and felder.get("is_admin") is False:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Das eigene Administratorrecht lässt sich nicht abgeben",
        )
    if eigenes and felder.get("is_active") is False:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Das eigene Konto lässt sich nicht sperren",
        )
    entzieht_admin = nutzer.is_admin and (
        felder.get("is_admin") is False or felder.get("is_active") is False
    )
    if entzieht_admin and _anzahl_admins(db) <= 1:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Der letzte Administrator lässt sich nicht entmachten",
        )

    for feld, wert in felder.items():
        setattr(nutzer, feld, wert)
    db.commit()
    # Sperren muss sofort wirken, sonst liefe die offene Sitzung weiter.
    if felder.get("is_active") is False:
        sitzungen_beenden(nutzer.id, db)
    db.refresh(nutzer)
    return nutzer


@router.delete("/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_user(
    user_id: int,
    db: Session = Depends(get_db),
    principal: Principal = Depends(nur_admin),
) -> None:
    nutzer = benutzer_oder_404(user_id, db)
    if nutzer.id == principal.user_id:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Das eigene Konto lässt sich nicht löschen",
        )
    if nutzer.is_admin and _anzahl_admins(db) <= 1:
        # Sonst kommt niemand mehr an die Verwaltung — außer über tools/admin_anlegen.py.
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Der letzte Administrator lässt sich nicht löschen",
        )
    eigene = list(db.scalars(select(Space).where(Space.owner_id == nutzer.id)))
    if eigene:
        # Ein Privatbereich ohne Eigentümer wäre für niemanden mehr sichtbar —
        # auch nicht für den Administrator. Also erst klären, wohin damit.
        # Übertragen geht bewusst nicht mehr (privat bleibt privat), es bleibt
        # das Löschen: leer über die Verwaltung, gefüllt über
        # `tools/bereich_entfernen.py`, ohne dass jemand hineinsieht.
        namen = ", ".join(f"„{s.name}“" for s in eigene)
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(f"Konto besitzt noch private Bereiche ({namen}) — " "diese bitte erst löschen"),
        )
    db.delete(nutzer)  # Freigaben und Sitzungen hängen per Cascade daran
    db.commit()


@router.put("/{user_id}/password", status_code=status.HTTP_204_NO_CONTENT)
def set_password(
    user_id: int,
    data: PasswordSet,
    request: Request,
    db: Session = Depends(get_db),
    principal: Principal = Depends(get_principal),
) -> None:
    """Setzt ein Passwort — als Administrator für jeden, sonst nur das eigene."""
    nutzer = benutzer_oder_404(user_id, db)
    eigenes = principal.user_id == nutzer.id
    if not principal.is_admin and not eigenes:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Nur das eigene Passwort lässt sich ändern",
        )
    # Wer sein eigenes Passwort ändert, muss das alte kennen. Ein Administrator
    # darf fremde zurücksetzen — sonst wäre ein vergessenes Passwort ein Fall
    # für die Kommandozeile.
    # `rechenplatz` deckelt die gleichzeitigen scrypt-Läufe — dieselbe Bremse
    # wie am Login, denn auch diese Route ist beliebig oft aufrufbar.
    with rechenplatz():
        altes_stimmt = not eigenes or hash_pruefen(data.altes_passwort or "", nutzer.password_hash)
    if not altes_stimmt:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Das alte Passwort stimmt nicht",
        )

    with rechenplatz():
        nutzer.password_hash = hash_erzeugen(data.neues_passwort)
    db.commit()
    # Alle anderen Sitzungen dieses Kontos fliegen raus; die eigene bleibt.
    sitzungen_beenden(nutzer.id, db, ausser=request.cookies.get(COOKIE_NAME) if eigenes else None)


def _anzahl_admins(db: Session) -> int:
    return db.scalar(select(func.count()).select_from(User).where(User.is_admin.is_(True))) or 0


# ── Freigaben je Bereich ────────────────────────────────────────────────────


@router.get("/permissions/{space_id}", response_model=list[PermissionRead])
def list_permissions(
    space_id: int,
    db: Session = Depends(get_db),
    _: Principal = Depends(nur_admin),
) -> list[SpacePermission]:
    _space_holen(space_id, db)
    return list(db.scalars(select(SpacePermission).where(SpacePermission.space_id == space_id)))


@router.put("/permissions/{space_id}", response_model=PermissionRead)
def set_permission(
    space_id: int,
    data: PermissionSet,
    db: Session = Depends(get_db),
    _: Principal = Depends(nur_admin),
) -> SpacePermission:
    """Legt die Freigabe an oder ändert ihre Stufe (idempotent)."""
    space = _space_holen(space_id, db)
    if space.is_private:
        # Privat heißt privat. Sonst hätte der Eigentümer eine Stelle, an der
        # er sein Versprechen versehentlich selbst aufhebt.
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Ein privater Bereich lässt sich nicht freigeben",
        )
    benutzer_oder_404(data.user_id, db)

    freigabe = db.scalar(
        select(SpacePermission).where(
            SpacePermission.space_id == space_id,
            SpacePermission.user_id == data.user_id,
        )
    )
    if freigabe is None:
        freigabe = SpacePermission(space_id=space_id, user_id=data.user_id, level=data.level)
        db.add(freigabe)
    else:
        freigabe.level = data.level
    db.commit()
    db.refresh(freigabe)
    return freigabe


@router.delete("/permissions/{space_id}/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
def revoke_permission(
    space_id: int,
    user_id: int,
    db: Session = Depends(get_db),
    _: Principal = Depends(nur_admin),
) -> None:
    _space_holen(space_id, db)
    freigabe = db.scalar(
        select(SpacePermission).where(
            SpacePermission.space_id == space_id,
            SpacePermission.user_id == user_id,
        )
    )
    if freigabe is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Freigabe nicht gefunden")
    db.delete(freigabe)
    db.commit()
