"""Tests der Anmeldung.

Zwei Welten in einer Datei:

* Die Passwortfunktionen und die Sitzungslogik werden direkt geprüft.
* Für die Routen schaltet die Fixture `mit_anmeldung` `AUTH_ENABLED=true` —
  nur innerhalb des jeweiligen Tests. Die übrigen 71 Tests laufen weiterhin im
  offenen Betrieb, und am laufenden System bleibt die Anmeldung bis zum
  bewussten Umschalten aus.
"""

from datetime import UTC, datetime, timedelta

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session
from src.anmeldeschutz import FREIVERSUCHE, absender
from src.auth import COOKIE_NAME
from src.models import Recht, Space, SpacePermission, User, UserSession
from src.passwoerter import hash_erzeugen, hash_pruefen, token_hashen


def _nutzer_anlegen(
    db: Session,
    username: str = "chef",
    passwort: str = "geheim12",
    *,
    admin: bool = True,
    aktiv: bool = True,
) -> User:
    nutzer = User(
        username=username,
        display_name=username.capitalize(),
        password_hash=hash_erzeugen(passwort),
        is_admin=admin,
        is_active=aktiv,
    )
    db.add(nutzer)
    db.commit()
    db.refresh(nutzer)
    return nutzer


# ── Passwörter ──────────────────────────────────────────────────────────────


def test_hash_rundlauf() -> None:
    hash_wert = hash_erzeugen("geheim12")
    assert hash_wert.startswith("scrypt$")
    assert "geheim12" not in hash_wert
    assert hash_pruefen("geheim12", hash_wert)
    assert not hash_pruefen("geheim13", hash_wert)


def test_hash_ist_gesalzen() -> None:
    assert hash_erzeugen("geheim12") != hash_erzeugen("geheim12")


def test_hash_pruefen_vertraegt_muell() -> None:
    assert not hash_pruefen("geheim12", None)
    assert not hash_pruefen("geheim12", "")
    assert not hash_pruefen("geheim12", "kein-hash")
    assert not hash_pruefen("geheim12", "scrypt$a$b$c$d$e")


# ── Anmelden und abmelden ───────────────────────────────────────────────────


def test_login_setzt_cookie_und_me_antwortet(
    client: TestClient, db_session: Session, mit_anmeldung: None
) -> None:
    _nutzer_anlegen(db_session)

    assert client.get("/api/auth/me").status_code == 401

    antwort = client.post("/api/auth/login", json={"username": "chef", "password": "geheim12"})
    assert antwort.status_code == 200
    assert antwort.json()["is_admin"] is True
    assert antwort.json()["ist_offener_betrieb"] is False
    assert COOKIE_NAME in client.cookies

    ich = client.get("/api/auth/me")
    assert ich.status_code == 200
    assert ich.json()["username"] == "chef"


def test_login_mit_falschem_passwort(
    client: TestClient, db_session: Session, mit_anmeldung: None
) -> None:
    _nutzer_anlegen(db_session)
    antwort = client.post("/api/auth/login", json={"username": "chef", "password": "falsch12"})
    assert antwort.status_code == 401
    # Dieselbe Meldung wie bei einem unbekannten Konto — sie verrät nichts.
    unbekannt = client.post("/api/auth/login", json={"username": "niemand", "password": "falsch12"})
    assert unbekannt.status_code == 401
    assert unbekannt.json()["detail"] == antwort.json()["detail"]


def test_gesperrtes_konto_kommt_nicht_hinein(
    client: TestClient, db_session: Session, mit_anmeldung: None
) -> None:
    _nutzer_anlegen(db_session, aktiv=False)
    assert (
        client.post(
            "/api/auth/login", json={"username": "chef", "password": "geheim12"}
        ).status_code
        == 401
    )


def test_logout_beendet_die_sitzung_wirklich(
    client: TestClient, db_session: Session, mit_anmeldung: None
) -> None:
    _nutzer_anlegen(db_session)
    client.post("/api/auth/login", json={"username": "chef", "password": "geheim12"})
    token = client.cookies[COOKIE_NAME]

    assert client.post("/api/auth/logout").status_code == 204
    assert db_session.query(UserSession).count() == 0

    # Selbst mit dem alten Token in der Hand kommt niemand mehr hinein.
    client.cookies.set(COOKIE_NAME, token)
    assert client.get("/api/auth/me").status_code == 401


def test_abgelaufene_sitzung_gilt_nicht(
    client: TestClient, db_session: Session, mit_anmeldung: None
) -> None:
    nutzer = _nutzer_anlegen(db_session)
    client.post("/api/auth/login", json={"username": "chef", "password": "geheim12"})

    sitzung = db_session.query(UserSession).filter(UserSession.user_id == nutzer.id).one()
    sitzung.expires_at = datetime.now(UTC).replace(tzinfo=None) - timedelta(minutes=1)
    db_session.commit()

    assert client.get("/api/auth/me").status_code == 401


def test_sitzung_verlaengert_sich(
    client: TestClient, db_session: Session, mit_anmeldung: None
) -> None:
    nutzer = _nutzer_anlegen(db_session)
    client.post("/api/auth/login", json={"username": "chef", "password": "geheim12"})

    sitzung = db_session.query(UserSession).filter(UserSession.user_id == nutzer.id).one()
    knapp = datetime.now(UTC).replace(tzinfo=None) + timedelta(hours=1)
    sitzung.expires_at = knapp
    db_session.commit()

    assert client.get("/api/auth/me").status_code == 200
    db_session.refresh(sitzung)
    assert sitzung.expires_at > knapp + timedelta(days=1)


def test_me_im_offenen_betrieb(client: TestClient) -> None:
    """Ohne AUTH_ENABLED antwortet /me trotzdem — mit gesetztem Merkmal."""
    antwort = client.get("/api/auth/me")
    assert antwort.status_code == 200
    assert antwort.json()["ist_offener_betrieb"] is True
    assert antwort.json()["id"] is None


def test_login_ohne_eingeschaltete_anmeldung(client: TestClient) -> None:
    antwort = client.post("/api/auth/login", json={"username": "chef", "password": "geheim12"})
    assert antwort.status_code == 400


# ── Benutzerverwaltung nur für Administratoren ──────────────────────────────


def _anmelden(client: TestClient, username: str, passwort: str = "geheim12") -> None:
    antwort = client.post("/api/auth/login", json={"username": username, "password": passwort})
    assert antwort.status_code == 200


def test_benutzerrouten_sind_admin_only(
    client: TestClient, db_session: Session, mit_anmeldung: None
) -> None:
    _nutzer_anlegen(db_session, "chef")
    _nutzer_anlegen(db_session, "lager1", admin=False)

    # Ohne Anmeldung: 401.
    assert client.get("/api/users").status_code == 401

    _anmelden(client, "lager1")
    assert client.get("/api/users").status_code == 403
    neu = {
        "username": "eindringling",
        "display_name": "X",
        "password": "geheim12",
        "is_admin": True,
    }
    assert client.post("/api/users", json=neu).status_code == 403

    client.post("/api/auth/logout")
    _anmelden(client, "chef")
    assert client.get("/api/users").status_code == 200
    assert client.post("/api/users", json=neu).status_code == 201


def test_letzter_admin_und_eigenes_konto_bleiben(
    client: TestClient, db_session: Session, mit_anmeldung: None
) -> None:
    chef = _nutzer_anlegen(db_session, "chef")
    lager = _nutzer_anlegen(db_session, "lager1", admin=False)
    _anmelden(client, "chef")

    # Das eigene Konto ist tabu — und es ist zugleich der letzte Administrator.
    assert client.delete(f"/api/users/{chef.id}").status_code == 409
    assert client.delete(f"/api/users/{lager.id}").status_code == 204


def test_passwort_aendern(client: TestClient, db_session: Session, mit_anmeldung: None) -> None:
    _nutzer_anlegen(db_session, "chef")
    lager = _nutzer_anlegen(db_session, "lager1", admin=False)

    # Selbst ändern: nur mit dem alten Passwort.
    _anmelden(client, "lager1")
    falsch = client.put(
        f"/api/users/{lager.id}/password",
        json={"altes_passwort": "daneben1", "neues_passwort": "neuneu12"},
    )
    assert falsch.status_code == 403
    richtig = client.put(
        f"/api/users/{lager.id}/password",
        json={"altes_passwort": "geheim12", "neues_passwort": "neuneu12"},
    )
    assert richtig.status_code == 204
    client.post("/api/auth/logout")
    _anmelden(client, "lager1", "neuneu12")

    # Fremdes Passwort ändern darf nur der Administrator.
    chef_id = db_session.query(User).filter(User.username == "chef").one().id
    assert (
        client.put(
            f"/api/users/{chef_id}/password", json={"neues_passwort": "andere12"}
        ).status_code
        == 403
    )
    client.post("/api/auth/logout")
    _anmelden(client, "chef")
    # Zurücksetzen ohne altes Passwort.
    assert (
        client.put(
            f"/api/users/{lager.id}/password", json={"neues_passwort": "reset123"}
        ).status_code
        == 204
    )
    client.post("/api/auth/logout")
    _anmelden(client, "lager1", "reset123")


def test_passwortwechsel_wirft_andere_sitzungen_raus(
    client: TestClient, db_session: Session, mit_anmeldung: None
) -> None:
    lager = _nutzer_anlegen(db_session, "lager1", admin=False)
    # Eine zweite, „andere" Sitzung desselben Kontos (anderes Gerät).
    db_session.add(
        UserSession(
            token_hash=token_hashen("anderes-geraet"),
            user_id=lager.id,
            expires_at=datetime.now(UTC).replace(tzinfo=None) + timedelta(days=30),
        )
    )
    db_session.commit()

    _anmelden(client, "lager1")
    client.put(
        f"/api/users/{lager.id}/password",
        json={"altes_passwort": "geheim12", "neues_passwort": "neuneu12"},
    )

    # Die eigene Sitzung lebt weiter, die andere ist weg.
    assert client.get("/api/auth/me").status_code == 200
    assert db_session.query(UserSession).count() == 1


# ── Bereichsrechte greifen mit eingeschalteter Anmeldung ────────────────────


def test_ohne_freigabe_kein_bereich(
    client: TestClient, db_session: Session, mit_anmeldung: None
) -> None:
    space = Space(key="lager", name="Lager")
    db_session.add(space)
    nutzer = _nutzer_anlegen(db_session, "lager1", admin=False)
    db_session.commit()

    _anmelden(client, "lager1")
    assert client.get("/api/spaces").json() == []

    db_session.add(SpacePermission(space_id=space.id, user_id=nutzer.id, level=Recht.LESEN))
    db_session.commit()
    sichtbar = client.get("/api/spaces").json()
    assert [b["key"] for b in sichtbar] == ["lager"]

    # Lesen reicht nicht zum Anlegen einer Seite.
    angelegt = client.post(
        "/api/pages",
        json={"space_id": space.id, "title": "Versuch", "body": "x"},
    )
    assert angelegt.status_code == 403


def test_autor_kommt_aus_der_anmeldung(
    client: TestClient, db_session: Session, mit_anmeldung: None
) -> None:
    space = Space(key="lager", name="Lager")
    db_session.add(space)
    _nutzer_anlegen(db_session, "chef")
    db_session.commit()

    _anmelden(client, "chef")
    seite = client.post(
        "/api/pages",
        # Der mitgeschickte Autor wird bewusst ignoriert.
        json={"space_id": space.id, "title": "Notiz", "body": "x", "author": "Jemand anderes"},
    ).json()

    versionen = client.get(f"/api/pages/{seite['id']}/versions").json()
    assert versionen[0]["author"] == "Chef"


# ── Bremse gegen Passwort-Raten ─────────────────────────────────────────────


def test_login_sperrt_nach_zu_vielen_fehlversuchen(
    client: TestClient, db_session: Session, mit_anmeldung: None
) -> None:
    """Nach den freien Versuchen antwortet der Login mit 429 statt mit 401.

    Ohne diese Bremse wäre ein achtstelliges Passwort im LAN durchprobierbar.
    """
    _nutzer_anlegen(db_session)

    falsch = {"username": "chef", "password": "daneben"}
    for _ in range(FREIVERSUCHE + 1):
        assert client.post("/api/auth/login", json=falsch).status_code == 401

    gesperrt = client.post("/api/auth/login", json=falsch)
    assert gesperrt.status_code == 429
    assert "Retry-After" in gesperrt.headers

    # Auch das richtige Passwort kommt jetzt nicht mehr durch — sonst ließe
    # sich die Sperre einfach durchtesten.
    richtig = client.post("/api/auth/login", json={"username": "chef", "password": "geheim12"})
    assert richtig.status_code == 429


def test_geglueckte_anmeldung_loescht_den_zaehler(
    client: TestClient, db_session: Session, mit_anmeldung: None
) -> None:
    _nutzer_anlegen(db_session)

    for _ in range(3):
        client.post("/api/auth/login", json={"username": "chef", "password": "daneben"})
    assert (
        client.post("/api/auth/login", json={"username": "chef", "password": "geheim12"})
    ).status_code == 200

    # Der Zähler ist zurückgesetzt: wieder volle Freiversuche, kein 429.
    for _ in range(FREIVERSUCHE):
        assert (
            client.post("/api/auth/login", json={"username": "chef", "password": "daneben"})
        ).status_code == 401


def test_absender_nimmt_den_letzten_forwarded_eintrag() -> None:
    """`X-Forwarded-For` wird von rechts gelesen.

    Vorne kann ein Angreifer beliebig auffüllen; der Proxy hängt die tatsächliche
    Gegenstelle hinten an. Läse man von links, sperrte man den Falschen aus.
    """

    class _Anfrage:
        headers = {"x-forwarded-for": "1.2.3.4, 203.0.113.7"}
        client = None

    assert absender(_Anfrage()) == "203.0.113.7"  # type: ignore[arg-type]
