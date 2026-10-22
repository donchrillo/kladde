"""API für Anmeldung und Abmeldung.

Drei Routen: `login` legt eine Sitzung an und setzt das Cookie, `logout` beendet
sie, `me` sagt dem Frontend, wer gerade unterwegs ist.

`me` antwortet auch im offenen Betrieb (`AUTH_ENABLED=false`) mit einem
sinnvollen Objekt — so braucht das Frontend keinen Sonderfall, sondern liest
`ist_offener_betrieb`.
"""

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..anmeldeschutz import erfolg, fehlschlag, pruefen, rechenplatz
from ..auth import (
    COOKIE_NAME,
    Principal,
    abgelaufene_aufraeumen,
    cookie_loeschen,
    cookie_setzen,
    get_principal,
    sitzung_anlegen,
    sitzung_beenden,
)
from ..config import get_settings
from ..database import get_db
from ..models import User
from ..passwoerter import hash_pruefen
from ..schemas import LoginRequest, MeRead

router = APIRouter()


@router.post("/login", response_model=MeRead)
def login(
    daten: LoginRequest,
    request: Request,
    response: Response,
    db: Session = Depends(get_db),
) -> MeRead:
    """Meldet an. Falsche Angaben ergeben immer dieselbe Meldung.

    Ob ein Benutzername existiert, verrät die Antwort bewusst nicht — deshalb
    ein einziger Fehlertext für „unbekannt", „falsches Passwort" und „gesperrt".

    Wiederholte Fehlversuche bremst `anmeldeschutz` aus (429), und die teure
    scrypt-Prüfung läuft nur mit begrenzter Parallelität.
    """
    if not get_settings().auth_enabled:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Die Anmeldung ist nicht eingeschaltet (AUTH_ENABLED=false)",
        )

    pruefen(request, daten.username)
    nutzer = db.scalar(select(User).where(User.username == daten.username))
    with rechenplatz():
        passwort_stimmt = hash_pruefen(daten.password, nutzer.password_hash if nutzer else None)
    if nutzer is None or not passwort_stimmt or not nutzer.is_active:
        fehlschlag(request, daten.username)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Benutzername oder Passwort falsch",
        )

    erfolg(request, daten.username)
    abgelaufene_aufraeumen(db)
    cookie_setzen(response, sitzung_anlegen(nutzer, db))
    return MeRead(
        id=nutzer.id,
        username=nutzer.username,
        display_name=nutzer.display_name,
        is_admin=nutzer.is_admin,
        darf_bereiche_anlegen=nutzer.darf_bereiche_anlegen,
        ist_offener_betrieb=False,
    )


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
def logout(request: Request, response: Response, db: Session = Depends(get_db)) -> None:
    """Beendet die Sitzung. Auch ohne gültiges Cookie ein stiller Erfolg."""
    sitzung_beenden(request.cookies.get(COOKIE_NAME), db)
    cookie_loeschen(response)


@router.get("/me", response_model=MeRead)
def me(principal: Principal = Depends(get_principal)) -> MeRead:
    return MeRead(
        id=principal.user_id,
        username=principal.username,
        display_name=principal.display_name,
        is_admin=principal.is_admin,
        darf_bereiche_anlegen=principal.darf_bereiche_anlegen,
        ist_offener_betrieb=principal.ist_offener_betrieb,
    )
