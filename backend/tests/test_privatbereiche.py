"""Tests der privaten Bereiche und der vierten Rechtestufe.

Fast alles hier braucht eine echte Anmeldung (`mit_anmeldung`): „privat" heißt
„gehört genau diesem Konto", und im offenen Betrieb gibt es kein Konto. Genau
deshalb steht am Ende auch ein Test, der beweist, dass der Rückweg
(`AUTH_ENABLED=false`) weiterhin alles öffnet — sonst wäre der Notausgang aus
Phase 2d stillschweigend verrammelt.
"""

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session
from src.models import Page, Recht, Space, SpacePermission, User
from src.passwoerter import hash_erzeugen
from src.search import indexieren


def _konto(
    db: Session,
    username: str,
    *,
    admin: bool = False,
    bereiche: bool = False,
) -> User:
    nutzer = User(
        username=username,
        display_name=username.capitalize(),
        password_hash=hash_erzeugen("geheim12"),
        is_admin=admin,
        darf_bereiche_anlegen=bereiche,
    )
    db.add(nutzer)
    db.commit()
    db.refresh(nutzer)
    return nutzer


def _anmelden(client: TestClient, username: str) -> None:
    antwort = client.post("/api/auth/login", json={"username": username, "password": "geheim12"})
    assert antwort.status_code == 200


def _privatbereich(db: Session, eigentuemer: User, *, mit_seite: str | None = None) -> Space:
    space = Space(
        key=f"privat-{eigentuemer.username}",
        name=f"Bereich {eigentuemer.username}",
        owner_id=eigentuemer.id,
        is_private=True,
    )
    db.add(space)
    db.commit()
    if mit_seite is not None:
        seite = Page(space_id=space.id, title=mit_seite, slug="geheim", body=mit_seite)
        db.add(seite)
        db.commit()
        # Von Hand indexieren: sonst stünde die Seite nicht im Volltextindex und
        # der Test "die Suche leckt nichts" wäre trivial erfüllt.
        indexieren(db, seite)
        db.commit()
    db.refresh(space)
    return space


# ── Was der Administrator nicht sieht ───────────────────────────────────────


def test_admin_kommt_nicht_in_fremden_privatbereich(
    client: TestClient, db_session: Session, mit_anmeldung: None
) -> None:
    anna = _konto(db_session, "anna")
    space = _privatbereich(db_session, anna, mit_seite="Gehaltsverhandlung")
    seite = db_session.query(Page).filter(Page.space_id == space.id).one()
    _konto(db_session, "chef", admin=True)
    _anmelden(client, "chef")

    # Nicht in der Bereichsliste …
    assert [s["key"] for s in client.get("/api/spaces").json()] == []
    # … und auch nicht über den direkten Weg.
    assert client.get(f"/api/spaces/{space.key}").status_code == 403
    assert client.get(f"/api/spaces/{space.key}/pages").status_code == 403
    assert client.get(f"/api/pages/{seite.id}").status_code == 403
    assert client.patch(f"/api/pages/{seite.id}", json={"title": "Neu"}).status_code == 403


def test_privatbereich_leckt_nicht_ueber_suche_und_uebersicht(
    client: TestClient, db_session: Session, mit_anmeldung: None
) -> None:
    anna = _konto(db_session, "anna")
    _privatbereich(db_session, anna, mit_seite="Gehaltsverhandlung")
    _konto(db_session, "chef", admin=True)
    _anmelden(client, "chef")

    assert client.get("/api/search", params={"q": "Gehaltsverhandlung"}).json() == []
    assert client.get("/api/recent").json() == []


def test_eigentuemer_sieht_und_bearbeitet_seinen_bereich(
    client: TestClient, db_session: Session, mit_anmeldung: None
) -> None:
    anna = _konto(db_session, "anna")
    space = _privatbereich(db_session, anna)
    _anmelden(client, "anna")

    assert [s["key"] for s in client.get("/api/spaces").json()] == [space.key]
    angelegt = client.post("/api/pages", json={"space_id": space.id, "title": "Meine Notiz"})
    assert angelegt.status_code == 201
    # Als Eigentümer hat er die volle Stufe, also auch Löschen.
    assert client.delete(f"/api/pages/{angelegt.json()['id']}").status_code == 204


def test_privatbereich_laesst_sich_nicht_freigeben(
    client: TestClient, db_session: Session, mit_anmeldung: None
) -> None:
    """Auch ein Administrator öffnet einen privaten Bereich nicht per Freigabe."""
    anna = _konto(db_session, "anna")
    bert = _konto(db_session, "bert")
    space = _privatbereich(db_session, anna)
    _konto(db_session, "chef", admin=True)

    _anmelden(client, "chef")
    abgelehnt = client.put(
        f"/api/users/permissions/{space.id}", json={"user_id": bert.id, "level": "lesen"}
    )
    assert abgelehnt.status_code == 409

    # Und die Eigentümerin selbst kommt an die Freigaben gar nicht erst heran:
    # das dürfen seit der Beschränkung nur Administratoren.
    _anmelden(client, "anna")
    assert (
        client.put(
            f"/api/users/permissions/{space.id}", json={"user_id": bert.id, "level": "lesen"}
        )
    ).status_code == 403


def test_verwaltungsliste_zeigt_metadaten_ohne_inhalt(
    client: TestClient, db_session: Session, mit_anmeldung: None
) -> None:
    anna = _konto(db_session, "anna")
    _privatbereich(db_session, anna, mit_seite="Gehaltsverhandlung")
    db_session.add(Space(key="lager", name="Lager"))
    db_session.commit()
    _konto(db_session, "chef", admin=True)
    _anmelden(client, "chef")

    zeilen = {s["key"]: s for s in client.get("/api/spaces/verwaltung").json()}
    assert zeilen["privat-anna"]["is_private"] is True
    assert zeilen["privat-anna"]["owner_name"] == "Anna"
    assert zeilen["privat-anna"]["seiten"] == 1
    assert zeilen["lager"]["is_private"] is False
    assert zeilen["lager"]["owner_name"] is None


def test_verwaltungsliste_ist_admin_only(
    client: TestClient, db_session: Session, mit_anmeldung: None
) -> None:
    _konto(db_session, "anna")
    _anmelden(client, "anna")
    assert client.get("/api/spaces/verwaltung").status_code == 403


def test_privatbereich_laesst_sich_nicht_uebertragen(
    client: TestClient, db_session: Session, mit_anmeldung: None
) -> None:
    """Ein fremder Privatbereich wechselt den Eigentümer nicht — auch nicht für den Chef.

    Früher durfte ein Administrator übertragen. Damit war die Zusage „privat ist
    privat" aber nur so viel wert wie sein Verzicht: er hätte sich selbst
    eintragen, lesen und zurücktragen können, ohne jede Spur.
    """
    anna = _konto(db_session, "anna")
    bert = _konto(db_session, "bert")
    space = _privatbereich(db_session, anna)
    _konto(db_session, "chef", admin=True)
    _anmelden(client, "chef")

    versuch = client.patch(
        f"/api/spaces/{space.key}", json={"name": space.name, "owner_id": bert.id}
    )
    assert versuch.status_code == 403
    db_session.refresh(space)
    assert space.owner_id == anna.id

    # Auch der Umweg über sich selbst führt nirgendwohin.
    assert client.patch(f"/api/spaces/{space.key}", json={"owner_id": None}).status_code == 403
    assert client.get(f"/api/spaces/{space.key}").status_code == 403
    db_session.refresh(space)
    assert space.owner_id == anna.id


def test_admin_loescht_leeren_privatbereich(
    client: TestClient, db_session: Session, mit_anmeldung: None
) -> None:
    anna = _konto(db_session, "anna")
    space = _privatbereich(db_session, anna)
    _konto(db_session, "chef", admin=True)
    _anmelden(client, "chef")

    assert client.delete(f"/api/spaces/{space.key}").status_code == 204


def test_konto_mit_privatbereich_laesst_sich_nicht_loeschen(
    client: TestClient, db_session: Session, mit_anmeldung: None
) -> None:
    anna = _konto(db_session, "anna")
    _privatbereich(db_session, anna)
    _konto(db_session, "chef", admin=True)
    _anmelden(client, "chef")

    abgelehnt = client.delete(f"/api/users/{anna.id}")
    assert abgelehnt.status_code == 409
    assert "löschen" in abgelehnt.json()["detail"]


# ── Die vierte Stufe ────────────────────────────────────────────────────────


def _mit_stufe(client: TestClient, db: Session, stufe: Recht) -> tuple[Space, Page]:
    """Legt Bereich, Seite und ein angemeldetes Konto mit genau dieser Stufe an."""
    anna = _konto(db, "anna")
    space = Space(key="lager", name="Lager")
    db.add(space)
    db.commit()
    seite = Page(space_id=space.id, title="Bestand", slug="bestand", body="Text")
    db.add_all([seite, SpacePermission(space_id=space.id, user_id=anna.id, level=stufe)])
    db.commit()
    db.refresh(space)
    db.refresh(seite)
    _anmelden(client, "anna")
    return space, seite


def test_schreiben_darf_aendern_aber_nicht_loeschen(
    client: TestClient, db_session: Session, mit_anmeldung: None
) -> None:
    _, seite = _mit_stufe(client, db_session, Recht.SCHREIBEN)

    assert client.patch(f"/api/pages/{seite.id}", json={"title": "Neu"}).status_code == 200
    assert client.delete(f"/api/pages/{seite.id}").status_code == 403


def test_loeschen_darf_loeschen(
    client: TestClient, db_session: Session, mit_anmeldung: None
) -> None:
    _, seite = _mit_stufe(client, db_session, Recht.LOESCHEN)
    assert client.delete(f"/api/pages/{seite.id}").status_code == 204


def test_bereichswechsel_braucht_loeschen_im_quellbereich(
    client: TestClient, db_session: Session, mit_anmeldung: None
) -> None:
    _, seite = _mit_stufe(client, db_session, Recht.SCHREIBEN)
    anna = db_session.query(User).filter(User.username == "anna").one()
    ziel = Space(key="archiv", name="Archiv")
    db_session.add(ziel)
    db_session.commit()
    db_session.add(SpacePermission(space_id=ziel.id, user_id=anna.id, level=Recht.SCHREIBEN))
    db_session.commit()
    db_session.refresh(ziel)

    # Schreiben im Ziel reicht nicht — aus dem Quellbereich verschwindet sie.
    assert client.patch(f"/api/pages/{seite.id}", json={"space_id": ziel.id}).status_code == 403

    freigabe = db_session.query(SpacePermission).filter_by(user_id=anna.id).first()
    assert freigabe is not None
    freigabe.level = Recht.LOESCHEN
    db_session.commit()
    assert client.patch(f"/api/pages/{seite.id}", json={"space_id": ziel.id}).status_code == 200


def test_umhaengen_im_selben_bereich_bleibt_schreiben(
    client: TestClient, db_session: Session, mit_anmeldung: None
) -> None:
    space, seite = _mit_stufe(client, db_session, Recht.SCHREIBEN)
    kind = client.post(
        "/api/pages", json={"space_id": space.id, "title": "Unterseite", "parent_id": seite.id}
    )
    assert kind.status_code == 201
    # Gliederungspflege ist kein Wegschaffen.
    umgehaengt = client.patch(f"/api/pages/{kind.json()['id']}", json={"parent_id": None})
    assert umgehaengt.status_code == 200


# ── Bereiche anlegen ────────────────────────────────────────────────────────


def test_ohne_recht_kein_neuer_bereich(
    client: TestClient, db_session: Session, mit_anmeldung: None
) -> None:
    _konto(db_session, "anna")
    _anmelden(client, "anna")
    assert client.post("/api/spaces", json={"name": "Lager"}).status_code == 403


def test_mit_recht_neuer_bereich_und_verwalten_darauf(
    client: TestClient, db_session: Session, mit_anmeldung: None
) -> None:
    _konto(db_session, "anna", bereiche=True)
    _anmelden(client, "anna")

    angelegt = client.post("/api/spaces", json={"name": "Lager"})
    assert angelegt.status_code == 201
    # Ohne die automatische Freigabe sähe sie ihren eigenen Bereich nicht.
    # Ihr Recht darin ist die volle Stufe — nachgefragt über die Bereichsliste,
    # denn an die Freigabetabelle kommen nur noch Administratoren.
    bereiche = client.get("/api/spaces").json()
    assert [s["key"] for s in bereiche] == ["lager"]
    assert bereiche[0]["mein_recht"] == "verwalten"


def test_reservierter_schluessel_wird_abgelehnt(client: TestClient) -> None:
    assert client.post("/api/spaces", json={"name": "Verwaltung"}).status_code == 409


# ── Konten anlegen und ändern ───────────────────────────────────────────────


def test_neues_konto_bekommt_privatbereich(client: TestClient) -> None:
    angelegt = client.post(
        "/api/users",
        json={"username": "anna", "display_name": "Anna Muster", "password": "geheim12"},
    )
    assert angelegt.status_code == 201

    bereiche = {s["key"]: s for s in client.get("/api/spaces/verwaltung").json()}
    assert bereiche["anna-muster"]["is_private"] is True
    assert bereiche["anna-muster"]["owner_id"] == angelegt.json()["id"]


def test_zweiter_gleicher_name_bekommt_freien_schluessel(client: TestClient) -> None:
    for username in ("anna1", "anna2"):
        client.post(
            "/api/users",
            json={"username": username, "display_name": "Anna Muster", "password": "geheim12"},
        )
    schluessel = sorted(s["key"] for s in client.get("/api/spaces/verwaltung").json())
    assert schluessel == ["anna-muster", "anna-muster-2"]


def test_konto_aendern(client: TestClient) -> None:
    nutzer = client.post(
        "/api/users",
        json={"username": "anna", "display_name": "Anna", "password": "geheim12"},
    ).json()

    geaendert = client.patch(
        f"/api/users/{nutzer['id']}",
        json={"display_name": "Anna Muster", "darf_bereiche_anlegen": True},
    )
    assert geaendert.status_code == 200
    assert geaendert.json()["display_name"] == "Anna Muster"
    assert geaendert.json()["darf_bereiche_anlegen"] is True
    # Nicht mitgeschickte Felder bleiben, wie sie waren.
    assert geaendert.json()["is_admin"] is False


def test_sperren_beendet_die_sitzungen(
    client: TestClient, db_session: Session, mit_anmeldung: None
) -> None:
    anna = _konto(db_session, "anna")
    _konto(db_session, "chef", admin=True)

    _anmelden(client, "anna")
    assert client.get("/api/auth/me").status_code == 200
    annas_cookies = dict(client.cookies)

    client.cookies.clear()
    _anmelden(client, "chef")
    assert client.patch(f"/api/users/{anna.id}", json={"is_active": False}).status_code == 200

    client.cookies.clear()
    client.cookies.update(annas_cookies)
    assert client.get("/api/auth/me").status_code == 401


def test_letzter_admin_bleibt_admin(
    client: TestClient, db_session: Session, mit_anmeldung: None
) -> None:
    chef = _konto(db_session, "chef", admin=True)
    zweiter = _konto(db_session, "chef2", admin=True)
    _anmelden(client, "chef")

    # Solange es zwei gibt, geht es.
    assert client.patch(f"/api/users/{zweiter.id}", json={"is_admin": False}).status_code == 200
    # Das eigene Recht gibt niemand ab — sonst stünde das Wiki ohne Verwaltung da.
    assert client.patch(f"/api/users/{chef.id}", json={"is_admin": False}).status_code == 409
    assert client.patch(f"/api/users/{chef.id}", json={"is_active": False}).status_code == 409


# ── Der Rückweg ─────────────────────────────────────────────────────────────


def test_offener_betrieb_sieht_auch_privatbereiche(client: TestClient, db_session: Session) -> None:
    """`AUTH_ENABLED=false` öffnet weiterhin alles — der Notausgang bleibt frei.

    Ohne diesen Zweig in `_recht_im_bereich()` wären die privaten Bereiche nach
    dem Rückweg für niemanden mehr erreichbar: es gibt dann keinen angemeldeten
    Eigentümer, der sie beanspruchen könnte.
    """
    anna = _konto(db_session, "anna")
    space = _privatbereich(db_session, anna, mit_seite="Gehaltsverhandlung")

    assert space.key in [s["key"] for s in client.get("/api/spaces").json()]
    assert client.get(f"/api/spaces/{space.key}/pages").status_code == 200
    assert len(client.get("/api/search", params={"q": "Gehaltsverhandlung"}).json()) == 1


# ── Umzug rührt fremde Privatbereiche nicht an ──────────────────────────────


def test_umzug_laesst_fremden_privatbereich_unberuehrt(
    client: TestClient, db_session: Session, mit_anmeldung: None
) -> None:
    """Ein Bereichswechsel schreibt Verweise um — aber nicht in fremdem Privatem.

    Anna verlinkt aus ihrem Privatbereich auf eine Seite im Bereich „it". Bert
    schiebt diese Seite nach „archiv". Sein Umzug darf Annas Text nicht
    anfassen: er darf ihren Bereich nicht einmal öffnen. Der Verweis dort zeigt
    danach ins Leere — das ist der kleinere Schaden gegenüber einer Änderung,
    die Anna nie veranlasst hat.
    """
    anna = _konto(db_session, "anna")
    bert = _konto(db_session, "bert")
    privat = _privatbereich(db_session, anna)

    it = Space(key="it", name="IT")
    archiv = Space(key="archiv", name="Archiv")
    db_session.add_all([it, archiv])
    db_session.commit()
    db_session.add_all(
        [
            SpacePermission(space_id=it.id, user_id=bert.id, level=Recht.LOESCHEN),
            SpacePermission(space_id=archiv.id, user_id=bert.id, level=Recht.SCHREIBEN),
            SpacePermission(space_id=it.id, user_id=anna.id, level=Recht.SCHREIBEN),
        ]
    )
    db_session.commit()

    _anmelden(client, "bert")
    ziel = client.post("/api/pages", json={"space_id": it.id, "title": "VPN"}).json()
    assert ziel["slug"] == "vpn"

    # Zwei Seiten verlinken dieselbe Zielseite: eine offene und eine private.
    _anmelden(client, "anna")
    offen = client.post(
        "/api/pages",
        json={"space_id": it.id, "title": "Handbuch", "body": "Siehe [VPN](/wiki/it/vpn)"},
    ).json()
    geheim = client.post(
        "/api/pages",
        json={"space_id": privat.id, "title": "Notizen", "body": "Siehe [VPN](/wiki/it/vpn)"},
    ).json()

    _anmelden(client, "bert")
    umzug = client.patch(f"/api/pages/{ziel['id']}", json={"space_id": archiv.id})
    assert umzug.status_code == 200

    # Die offene Seite wurde nachgezogen — und zwar nachvollziehbar.
    _anmelden(client, "anna")
    danach = client.get(f"/api/pages/{offen['id']}").json()
    assert "/wiki/archiv/vpn" in danach["body"]
    versionen = client.get(f"/api/pages/{offen['id']}/versions").json()
    assert "Umzug nach „Archiv“ durch Bert" == versionen[0]["author"]

    # Der Privatbereich blieb unangetastet: alter Text, keine neue Revision.
    unberuehrt = client.get(f"/api/pages/{geheim['id']}").json()
    assert unberuehrt["body"] == "Siehe [VPN](/wiki/it/vpn)"
    assert len(client.get(f"/api/pages/{geheim['id']}/versions").json()) == 1
