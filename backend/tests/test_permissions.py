"""Tests der Rechte-Grundlage.

Die Anmeldung ist noch aus (`AUTH_ENABLED=false`), das Wiki verhält sich also
offen. Getestet wird hier deshalb zweierlei: dass der offene Betrieb
funktioniert, und dass die Rechte-Logik selbst korrekt entscheidet — sie wird
in Phase 2d nur noch angeschaltet, nicht mehr geschrieben.
"""

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session
from src.auth import OFFENER_PRINCIPAL, Principal, lesbare_space_ids, pruefe_bereich
from src.models import Recht, Space, SpacePermission, User
from src.passwoerter import hash_erzeugen


def test_offener_betrieb_darf_alles(client: TestClient) -> None:
    space = client.post("/api/spaces", json={"name": "Geschäftsleitung"})
    assert space.status_code == 201
    assert client.get("/api/spaces").status_code == 200


def test_benutzer_anlegen_und_auflisten(client: TestClient) -> None:
    angelegt = client.post(
        "/api/users",
        json={"username": "lager1", "display_name": "Lager Eins", "password": "geheim12"},
    )
    assert angelegt.status_code == 201
    assert angelegt.json()["is_admin"] is False

    doppelt = client.post(
        "/api/users",
        json={"username": "lager1", "display_name": "Noch mal", "password": "geheim12"},
    )
    assert doppelt.status_code == 409

    assert [u["username"] for u in client.get("/api/users").json()] == ["lager1"]


def test_freigabe_setzen_aendern_entziehen(client: TestClient) -> None:
    space = client.post("/api/spaces", json={"name": "Lager"}).json()
    nutzer = client.post(
        "/api/users",
        json={"username": "lager1", "display_name": "Lager Eins", "password": "geheim12"},
    ).json()

    gesetzt = client.put(
        f"/api/users/permissions/{space['id']}",
        json={"user_id": nutzer["id"], "level": "lesen"},
    )
    assert gesetzt.status_code == 200
    assert gesetzt.json()["level"] == "lesen"

    # Erneutes Setzen ändert die Stufe, statt eine zweite Zeile anzulegen.
    geaendert = client.put(
        f"/api/users/permissions/{space['id']}",
        json={"user_id": nutzer["id"], "level": "schreiben"},
    )
    assert geaendert.json()["id"] == gesetzt.json()["id"]
    assert geaendert.json()["level"] == "schreiben"
    assert len(client.get(f"/api/users/permissions/{space['id']}").json()) == 1

    assert client.delete(f"/api/users/permissions/{space['id']}/{nutzer['id']}").status_code == 204
    assert client.get(f"/api/users/permissions/{space['id']}").json() == []


# ── Die Entscheidungslogik selbst ───────────────────────────────────────────


def _aufbau(db: Session) -> tuple[Space, User]:
    space = Space(key="lager", name="Lager")
    nutzer = User(username="lager1", display_name="Lager Eins")
    db.add_all([space, nutzer])
    db.commit()
    return space, nutzer


def test_ohne_freigabe_kein_zugriff(db_session: Session) -> None:
    space, nutzer = _aufbau(db_session)
    fremder = Principal(user_id=nutzer.id, username="lager1", display_name="Lager1", is_admin=False)

    with pytest.raises(HTTPException) as fehler:
        pruefe_bereich(fremder, space.id, Recht.LESEN, db_session)
    assert fehler.value.status_code == 403


def test_lesen_reicht_nicht_zum_schreiben(db_session: Session) -> None:
    space, nutzer = _aufbau(db_session)
    db_session.add(SpacePermission(space_id=space.id, user_id=nutzer.id, level=Recht.LESEN))
    db_session.commit()
    principal = Principal(
        user_id=nutzer.id, username="lager1", display_name="Lager1", is_admin=False
    )

    pruefe_bereich(principal, space.id, Recht.LESEN, db_session)  # geht
    with pytest.raises(HTTPException) as fehler:
        pruefe_bereich(principal, space.id, Recht.SCHREIBEN, db_session)
    assert fehler.value.status_code == 403


def test_verwalten_schliesst_die_stufen_darunter_ein(db_session: Session) -> None:
    space, nutzer = _aufbau(db_session)
    db_session.add(SpacePermission(space_id=space.id, user_id=nutzer.id, level=Recht.VERWALTEN))
    db_session.commit()
    principal = Principal(
        user_id=nutzer.id, username="lager1", display_name="Lager1", is_admin=False
    )

    for stufe in (Recht.LESEN, Recht.SCHREIBEN, Recht.VERWALTEN):
        pruefe_bereich(principal, space.id, stufe, db_session)


def test_administrator_kommt_ueberall_hin(db_session: Session) -> None:
    space, _ = _aufbau(db_session)
    chef = Principal(user_id=99, username="chef", display_name="Chef", is_admin=True)
    pruefe_bereich(chef, space.id, Recht.VERWALTEN, db_session)


def test_lesbare_bereiche(db_session: Session) -> None:
    space, nutzer = _aufbau(db_session)
    zweiter = Space(key="chef", name="Geschäftsleitung")
    db_session.add(zweiter)
    db_session.commit()
    db_session.add(SpacePermission(space_id=space.id, user_id=nutzer.id, level=Recht.LESEN))
    db_session.commit()

    principal = Principal(
        user_id=nutzer.id, username="lager1", display_name="Lager1", is_admin=False
    )
    assert lesbare_space_ids(principal, db_session) == [space.id]
    # None heißt "alle" — der Aufrufer lässt den Filter dann weg.
    assert lesbare_space_ids(OFFENER_PRINCIPAL, db_session) is None


def test_verwalten_allein_reicht_nicht_zum_freigeben(
    client: TestClient, db_session: Session, mit_anmeldung: None
) -> None:
    """Freigaben sind Administratorensache — auch im eigenen Bereich.

    `verwalten` bleibt die Vorbereitung für Bereichsverantwortliche, aber es
    gibt keine Oberfläche dafür; erreichbar wäre die Fähigkeit nur mit einem
    selbst gebauten Aufruf, und der verriete nebenbei, welche Konto-IDs es gibt.
    """
    anna = User(
        username="anna",
        display_name="Anna",
        password_hash=hash_erzeugen("geheim12"),
        is_admin=False,
    )
    bert = User(
        username="bert",
        display_name="Bert",
        password_hash=hash_erzeugen("geheim12"),
        is_admin=False,
    )
    space = Space(key="it", name="IT")
    db_session.add_all([anna, bert, space])
    db_session.commit()
    db_session.add(SpacePermission(space_id=space.id, user_id=anna.id, level=Recht.VERWALTEN))
    db_session.commit()

    assert (
        client.post("/api/auth/login", json={"username": "anna", "password": "geheim12"})
    ).status_code == 200

    # Sie darf im Bereich alles — nur nicht bestimmen, wer sonst hinein darf.
    assert client.get(f"/api/spaces/{space.key}").json()["mein_recht"] == "verwalten"
    assert client.patch(f"/api/spaces/{space.key}", json={"name": "IT-Büro"}).status_code == 200

    assert client.get(f"/api/users/permissions/{space.id}").status_code == 403
    freigabe = client.put(
        f"/api/users/permissions/{space.id}", json={"user_id": bert.id, "level": "lesen"}
    )
    assert freigabe.status_code == 403
    assert client.delete(f"/api/users/permissions/{space.id}/{bert.id}").status_code == 403
