"""Tests für Schlagwörter, Rückverweise, Versionsvergleich und Übersicht."""

from fastapi.testclient import TestClient


def _seite(client: TestClient, space_id: int, titel: str, body: str = "") -> dict:
    antwort = client.post("/api/pages", json={"space_id": space_id, "title": titel, "body": body})
    assert antwort.status_code == 201, antwort.text
    return dict(antwort.json())


def _bereich(client: TestClient, name: str = "Handbuch") -> dict:
    return dict(client.post("/api/spaces", json={"name": name}).json())


# ── Schlagwörter ────────────────────────────────────────────────────────────


def test_schlagwoerter_setzen_und_normalisieren(client: TestClient) -> None:
    space = _bereich(client)
    seite = _seite(client, space["id"], "Drucker")

    antwort = client.put(
        f"/api/pages/{seite['id']}/labels",
        json={"names": ["  Drucker ", "HARDWARE", "drucker", "  "]},
    )
    assert antwort.status_code == 200
    # Klein geschrieben, entdoppelt, Leereinträge weg, sortiert.
    assert antwort.json()["labels"] == ["drucker", "hardware"]


def test_schlagwoerter_ersetzen_statt_ergaenzen(client: TestClient) -> None:
    space = _bereich(client)
    seite = _seite(client, space["id"], "Drucker")

    client.put(f"/api/pages/{seite['id']}/labels", json={"names": ["alt"]})
    antwort = client.put(f"/api/pages/{seite['id']}/labels", json={"names": ["neu"]})
    assert antwort.json()["labels"] == ["neu"]


def test_schlagwortliste_mit_anzahl(client: TestClient) -> None:
    space = _bereich(client)
    eins = _seite(client, space["id"], "Drucker")
    zwei = _seite(client, space["id"], "Scanner")
    client.put(f"/api/pages/{eins['id']}/labels", json={"names": ["hardware", "it"]})
    client.put(f"/api/pages/{zwei['id']}/labels", json={"names": ["hardware"]})

    liste = client.get("/api/labels").json()
    assert liste[0] == {"name": "hardware", "anzahl": 2}
    assert {"name": "it", "anzahl": 1} in liste


def test_seiten_zu_schlagwort(client: TestClient) -> None:
    space = _bereich(client)
    seite = _seite(client, space["id"], "Drucker")
    client.put(f"/api/pages/{seite['id']}/labels", json={"names": ["hardware"]})

    treffer = client.get("/api/labels/HARDWARE/pages").json()
    assert [t["title"] for t in treffer] == ["Drucker"]
    assert client.get("/api/labels/gibtsnicht/pages").json() == []


# ── Rückverweise ────────────────────────────────────────────────────────────


def test_rueckverweise(client: TestClient) -> None:
    space = _bereich(client)
    ziel = _seite(client, space["id"], "VPN")
    _seite(
        client,
        space["id"],
        "Einstieg",
        f"Siehe [VPN](/wiki/{space['key']}/{ziel['slug']}) für Details.",
    )

    verweise = client.get(f"/api/pages/{ziel['id']}/backlinks").json()
    assert [v["title"] for v in verweise] == ["Einstieg"]


def test_rueckverweis_verschwindet_wenn_link_entfernt(client: TestClient) -> None:
    space = _bereich(client)
    ziel = _seite(client, space["id"], "VPN")
    quelle = _seite(client, space["id"], "Einstieg", f"[VPN](/wiki/{space['key']}/{ziel['slug']})")
    assert len(client.get(f"/api/pages/{ziel['id']}/backlinks").json()) == 1

    client.patch(f"/api/pages/{quelle['id']}", json={"body": "Kein Link mehr."})
    assert client.get(f"/api/pages/{ziel['id']}/backlinks").json() == []


def test_selbstverweis_wird_nicht_gezaehlt(client: TestClient) -> None:
    space = _bereich(client)
    seite = _seite(client, space["id"], "VPN")
    client.patch(
        f"/api/pages/{seite['id']}",
        json={"body": f"[hierher](/wiki/{space['key']}/{seite['slug']})"},
    )
    assert client.get(f"/api/pages/{seite['id']}/backlinks").json() == []


# ── Versionen ───────────────────────────────────────────────────────────────


def test_vergleich_zweier_revisionen(client: TestClient) -> None:
    space = _bereich(client)
    seite = _seite(client, space["id"], "Drucker", "Zeile eins\nZeile zwei")
    client.patch(f"/api/pages/{seite['id']}", json={"body": "Zeile eins\nZeile drei"})

    diff = client.get(f"/api/pages/{seite['id']}/versions/1/diff", params={"gegen": 2}).json()
    assert diff["von_revision"] == 1 and diff["nach_revision"] == 2
    arten = {(z["art"], z["text"]) for z in diff["zeilen"]}
    assert ("gleich", "Zeile eins") in arten
    assert ("minus", "Zeile zwei") in arten
    assert ("plus", "Zeile drei") in arten


def test_vergleich_sortiert_die_revisionen(client: TestClient) -> None:
    """Reihenfolge in der Anfrage egal — die ältere ist immer links."""
    space = _bereich(client)
    seite = _seite(client, space["id"], "Drucker", "alt")
    client.patch(f"/api/pages/{seite['id']}", json={"body": "neu"})

    diff = client.get(f"/api/pages/{seite['id']}/versions/2/diff", params={"gegen": 1}).json()
    assert diff["von_revision"] == 1 and diff["nach_revision"] == 2


def test_unbekannte_revision_im_vergleich(client: TestClient) -> None:
    space = _bereich(client)
    seite = _seite(client, space["id"], "Drucker", "x")
    antwort = client.get(f"/api/pages/{seite['id']}/versions/1/diff", params={"gegen": 99})
    assert antwort.status_code == 404


def test_revision_zurueckholen_legt_neue_revision_an(client: TestClient) -> None:
    space = _bereich(client)
    seite = _seite(client, space["id"], "Drucker", "Ursprung")
    client.patch(f"/api/pages/{seite['id']}", json={"body": "Versehentlich geloescht"})

    zurueck = client.post(f"/api/pages/{seite['id']}/versions/1/restore")
    assert zurueck.status_code == 200
    assert zurueck.json()["body"] == "Ursprung"

    # Historie bleibt vollstaendig: 1 Ursprung, 2 Versehen, 3 zurueckgeholt.
    versionen = client.get(f"/api/pages/{seite['id']}/versions").json()
    assert [v["revision"] for v in versionen] == [3, 2, 1]


def test_zurueckholen_pflegt_den_suchindex(client: TestClient) -> None:
    space = _bereich(client)
    seite = _seite(client, space["id"], "Drucker", "Tonerwechsel erklaert")
    client.patch(f"/api/pages/{seite['id']}", json={"body": "Nichts mehr"})
    assert client.get("/api/search", params={"q": "Tonerwechsel"}).json() == []

    client.post(f"/api/pages/{seite['id']}/versions/1/restore")
    assert client.get("/api/search", params={"q": "Tonerwechsel"}).json() != []


# ── Zuletzt geändert ────────────────────────────────────────────────────────


def test_zuletzt_geaendert(client: TestClient) -> None:
    space = _bereich(client)
    _seite(client, space["id"], "Erste")
    zweite = _seite(client, space["id"], "Zweite")
    client.patch(f"/api/pages/{zweite['id']}", json={"body": "aktualisiert"})

    liste = client.get("/api/recent", params={"limit": 5}).json()
    assert liste[0]["title"] == "Zweite"
    assert liste[0]["space_name"] == "Handbuch"


# ── Suche mit Bereichsfilter ────────────────────────────────────────────────


def test_suche_auf_bereich_einschraenken(client: TestClient) -> None:
    eins = _bereich(client, "Handbuch")
    zwei = _bereich(client, "Lager")
    _seite(client, eins["id"], "Drucker im Buero")
    _seite(client, zwei["id"], "Drucker im Lager")

    assert len(client.get("/api/search", params={"q": "Drucker"}).json()) == 2
    nur_lager = client.get("/api/search", params={"q": "Drucker", "space_id": zwei["id"]}).json()
    assert [t["title"] for t in nur_lager] == ["Drucker im Lager"]
