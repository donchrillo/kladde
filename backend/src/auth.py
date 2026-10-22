"""Anmeldung und Berechtigungen.

Der Kern ist der `Principal`: wer stellt gerade die Anfrage. Solange
`AUTH_ENABLED=false` ist, liefert die Dependency einen offenen Principal mit
Administratorrechten — das Wiki verhält sich dann wie ein offenes LAN-Wiki.

Mit `AUTH_ENABLED=true` kommt der Principal aus einer Sitzung: das Cookie trägt
ein Zufallstoken, in der Tabelle `user_session` liegt dessen SHA-256. Sitzungen
in der Datenbank statt eines JWT, damit Abmelden, Passwortwechsel und Sperren
sofort wirken.

Alle Routen laufen unabhängig davon schon immer durch `pruefe_bereich()`.
"""

import secrets
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from fastapi import Depends, HTTPException, Request, Response, status
from sqlalchemy import delete, or_, select
from sqlalchemy.orm import Session

from .config import get_settings
from .database import get_db
from .models import RANG, Recht, Space, SpacePermission, User, UserSession
from .passwoerter import token_hashen

# Name des Sitzungs-Cookies. Kein Punkt und kein Präfix — same-origin hinter Caddy.
COOKIE_NAME = "kladde_session"


def _jetzt() -> datetime:
    """UTC ohne Zeitzonenangabe, passend zu den übrigen Zeitstempeln."""
    return datetime.now(UTC).replace(tzinfo=None)


@dataclass(frozen=True)
class Principal:
    """Der Handelnde einer Anfrage."""

    user_id: int | None
    username: str
    display_name: str
    is_admin: bool
    darf_bereiche_anlegen: bool = False

    @property
    def ist_offener_betrieb(self) -> bool:
        """True, solange ohne Anmeldung gearbeitet wird."""
        return self.user_id is None


# Wer ohne eingeschaltete Anmeldung unterwegs ist. Bewusst Administrator, damit
# sich das Wiki im LAN wie ein offenes Wiki verhält.
OFFENER_PRINCIPAL = Principal(
    user_id=None,
    username="anonym",
    display_name="Offener Betrieb",
    is_admin=True,
    darf_bereiche_anlegen=True,
)


# ── Sitzungen ───────────────────────────────────────────────────────────────


def sitzung_anlegen(nutzer: User, db: Session) -> str:
    """Legt eine Sitzung an und gibt das Klartext-Token fürs Cookie zurück.

    Gespeichert wird nur der Hash; das Token selbst gibt es genau einmal — hier.
    """
    token = secrets.token_urlsafe(32)
    gueltig_bis = _jetzt() + timedelta(days=get_settings().session_days)
    db.add(UserSession(token_hash=token_hashen(token), user_id=nutzer.id, expires_at=gueltig_bis))
    db.commit()
    return token


def sitzung_beenden(token: str | None, db: Session) -> None:
    """Löscht die Sitzung zu diesem Token, falls es eine gibt."""
    if not token:
        return
    db.execute(delete(UserSession).where(UserSession.token_hash == token_hashen(token)))
    db.commit()


def sitzungen_beenden(user_id: int, db: Session, ausser: str | None = None) -> None:
    """Beendet alle Sitzungen eines Benutzers, optional bis auf die eigene."""
    abfrage = delete(UserSession).where(UserSession.user_id == user_id)
    if ausser:
        abfrage = abfrage.where(UserSession.token_hash != token_hashen(ausser))
    db.execute(abfrage)
    db.commit()


def abgelaufene_aufraeumen(db: Session) -> None:
    """Entfernt abgelaufene Sitzungen. Läuft beim Anmelden mit."""
    db.execute(delete(UserSession).where(UserSession.expires_at < _jetzt()))
    db.commit()


def cookie_setzen(response: Response, token: str) -> None:
    """Schreibt das Sitzungs-Cookie in die Antwort."""
    einstellungen = get_settings()
    response.set_cookie(
        COOKIE_NAME,
        token,
        max_age=einstellungen.session_days * 86400,
        httponly=True,
        secure=einstellungen.cookie_secure,
        samesite="lax",
        path="/",
    )


def cookie_loeschen(response: Response) -> None:
    response.delete_cookie(COOKIE_NAME, path="/")


def _nicht_angemeldet() -> HTTPException:
    """401 — im Frontend der Auslöser für die Anmeldemaske.

    Bewusst nicht 403: das hieße „angemeldet, aber nicht berechtigt".
    """
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Nicht angemeldet",
    )


def get_principal(
    request: Request,
    response: Response,
    db: Session = Depends(get_db),
) -> Principal:
    """FastAPI-Dependency: ermittelt den Handelnden der aktuellen Anfrage."""
    einstellungen = get_settings()
    if not einstellungen.auth_enabled:
        return OFFENER_PRINCIPAL

    token = request.cookies.get(COOKIE_NAME)
    if not token:
        raise _nicht_angemeldet()

    sitzung = db.scalar(select(UserSession).where(UserSession.token_hash == token_hashen(token)))
    jetzt = _jetzt()
    if sitzung is None or sitzung.expires_at < jetzt:
        raise _nicht_angemeldet()

    nutzer = db.get(User, sitzung.user_id)
    if nutzer is None or not nutzer.is_active:
        raise _nicht_angemeldet()

    # Rollierend verlängern, aber höchstens einmal am Tag schreiben.
    volle_frist = jetzt + timedelta(days=einstellungen.session_days)
    if sitzung.expires_at < volle_frist - timedelta(days=1):
        sitzung.expires_at = volle_frist
        db.commit()
        cookie_setzen(response, token)

    return Principal(
        user_id=nutzer.id,
        username=nutzer.username,
        display_name=nutzer.display_name,
        is_admin=nutzer.is_admin,
        darf_bereiche_anlegen=nutzer.darf_bereiche_anlegen,
    )


def nur_admin(principal: Principal = Depends(get_principal)) -> Principal:
    """Dependency für Routen, die ausschließlich Administratoren offenstehen."""
    if not principal.is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Nur für Administratoren",
        )
    return principal


# ── Bereichsrechte ──────────────────────────────────────────────────────────


def _recht_aus(principal: Principal, space: Space, freigabe: Recht | None) -> Recht | None:
    """Die Entscheidungsregel selbst, ohne Datenbankzugriff.

    Die einzige Stelle mit dem Administrator-Kurzschluss — und damit die
    einzige, an der private Bereiche dichtgemacht werden müssen. `freigabe` ist
    die eingetragene Stufe des Principals in diesem Bereich, falls es eine gibt.
    """
    if space.is_private:
        # Privater Bereich: nur der Eigentümer, ohne Ausnahme. Auch kein
        # Administrator — das ist der ganze Sinn der Sache.
        return Recht.VERWALTEN if space.owner_id == principal.user_id else None

    if principal.is_admin:
        return Recht.VERWALTEN
    return freigabe


def _recht_im_bereich(principal: Principal, space_id: int, db: Session) -> Recht | None:
    """Das stärkste Recht des Principals in diesem Bereich, oder None."""
    # Offener Betrieb (AUTH_ENABLED=false) kennt überhaupt keine Rechte. Ohne
    # diesen Zweig wären nach dem Rückweg die privaten Bereiche für niemanden
    # mehr erreichbar — es gibt dann ja keinen angemeldeten Eigentümer.
    if principal.user_id is None:
        return Recht.VERWALTEN if principal.is_admin else None

    space = db.get(Space, space_id)
    if space is None:
        return None

    freigabe = db.scalar(
        select(SpacePermission.level).where(
            SpacePermission.space_id == space_id,
            SpacePermission.user_id == principal.user_id,
        )
    )
    return _recht_aus(principal, space, freigabe)


def recht_im_bereich(principal: Principal, space_id: int, db: Session) -> Recht | None:
    """Wie `_recht_im_bereich`, für Aufrufer außerhalb dieses Moduls.

    Die Router brauchen das Recht nicht nur zum Prüfen, sondern auch zum
    Ausliefern: die Oberfläche soll gar nicht erst anbieten, was ohnehin im 403
    endet.
    """
    return _recht_im_bereich(principal, space_id, db)


def rechte_je_bereich(
    principal: Principal, spaces: list[Space], db: Session
) -> dict[int, Recht | None]:
    """Dasselbe für viele Bereiche auf einmal — eine Abfrage statt einer je Bereich.

    Für die Bereichsliste, die dem Frontend sagt, welche Bedienelemente es
    überhaupt anbieten darf.
    """
    if principal.user_id is None:
        offen = Recht.VERWALTEN if principal.is_admin else None
        return {space.id: offen for space in spaces}

    freigaben: dict[int, Recht] = {
        space_id: level
        for space_id, level in db.execute(
            select(SpacePermission.space_id, SpacePermission.level).where(
                SpacePermission.user_id == principal.user_id
            )
        )
    }
    return {space.id: _recht_aus(principal, space, freigaben.get(space.id)) for space in spaces}


def pruefe_bereich(
    principal: Principal,
    space_id: int,
    noetig: Recht,
    db: Session,
) -> None:
    """Wirft 403, wenn der Principal im Bereich nicht mindestens `noetig` hat."""
    vorhanden = _recht_im_bereich(principal, space_id, db)
    if vorhanden is None or RANG[vorhanden] < RANG[noetig]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Keine Berechtigung für diesen Bereich",
        )


def lesbare_space_ids(principal: Principal, db: Session) -> list[int] | None:
    """IDs aller lesbaren Bereiche — oder None, wenn alle lesbar sind.

    `None` statt einer vollständigen Liste, damit Aufrufer den Filter ganz
    weglassen können. Das gilt seit den privaten Bereichen nur noch im offenen
    Betrieb: ein Administrator liest zwar jeden offenen Bereich, aber keinen
    fremden privaten — sonst leckten Suche, Übersicht und Rückverweise genau
    das, was privat sein soll.
    """
    if principal.user_id is None:
        return None if principal.is_admin else []

    if principal.is_admin:
        return list(
            db.scalars(
                select(Space.id).where(
                    or_(Space.is_private.is_(False), Space.owner_id == principal.user_id)
                )
            )
        )

    # Freigaben zählen nur auf offenen Bereichen — private lassen sich gar nicht
    # freigeben, aber der Join hält auch Altlasten aus der Rechnung heraus.
    ueber_freigabe = (
        select(SpacePermission.space_id)
        .join(SpacePermission.space)
        .where(
            SpacePermission.user_id == principal.user_id,
            Space.is_private.is_(False),
        )
    )
    eigene_private = select(Space.id).where(
        Space.is_private.is_(True), Space.owner_id == principal.user_id
    )
    return list(db.scalars(ueber_freigabe)) + list(db.scalars(eigene_private))


def sichtbare_bereiche(principal: Principal, db: Session) -> list[Space]:
    """Alle Bereiche, die der Principal lesen darf, nach Namen sortiert."""
    abfrage = select(Space).order_by(Space.name)
    erlaubt = lesbare_space_ids(principal, db)
    if erlaubt is not None:
        abfrage = abfrage.where(Space.id.in_(erlaubt))
    return list(db.scalars(abfrage))


def benutzer_oder_404(user_id: int, db: Session) -> User:
    nutzer = db.get(User, user_id)
    if nutzer is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Benutzer nicht gefunden")
    return nutzer
