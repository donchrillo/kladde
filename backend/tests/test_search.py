"""Tests der Volltextsuche."""

from fastapi.testclient import TestClient


def _bereich_mit_seiten(client: TestClient) -> int:
    space = client.post("/api/spaces", json={"name": "Handbuch"}).json()
    client.post(
        "/api/pages",
        json={
            "space_id": space["id"],
            "title": "Drucker einrichten",
            "body": "Den Netzwerkdrucker über die Systemsteuerung hinzufügen.",
        },
    )
    client.post(
        "/api/pages",
        json={
            "space_id": space["id"],
            "title": "VPN",
            "body": "VPN-Zugang für das Büro beantragen.",
        },
    )
    return int(space["id"])


def test_findet_treffer_im_titel(client: TestClient) -> None:
    _bereich_mit_seiten(client)
    treffer = client.get("/api/search", params={"q": "Drucker"}).json()
    assert [t["title"] for t in treffer] == ["Drucker einrichten"]


def test_findet_treffer_im_text(client: TestClient) -> None:
    _bereich_mit_seiten(client)
    treffer = client.get("/api/search", params={"q": "VPN"}).json()
    assert [t["title"] for t in treffer] == ["VPN"]


def test_praefixsuche(client: TestClient) -> None:
    """'system' soll auch 'Systemsteuerung' finden."""
    _bereich_mit_seiten(client)
    treffer = client.get("/api/search", params={"q": "system"}).json()
    assert [t["title"] for t in treffer] == ["Drucker einrichten"]


def test_treffer_nennt_bereich_und_ausschnitt(client: TestClient) -> None:
    _bereich_mit_seiten(client)
    treffer = client.get("/api/search", params={"q": "Netzwerkdrucker"}).json()
    assert len(treffer) == 1
    assert treffer[0]["space_name"] == "Handbuch"
    assert treffer[0]["space_key"] == "handbuch"
    assert "Netzwerkdrucker" in treffer[0]["excerpt"]


def test_leere_suche_liefert_nichts(client: TestClient) -> None:
    _bereich_mit_seiten(client)
    assert client.get("/api/search", params={"q": "   "}).json() == []


def test_ohne_treffer_leere_liste(client: TestClient) -> None:
    _bereich_mit_seiten(client)
    assert client.get("/api/search", params={"q": "Buchhaltung"}).json() == []


def test_sonderzeichen_brechen_die_abfrage_nicht(client: TestClient) -> None:
    """FTS5-Syntax aus der Eingabe darf keinen Fehler auslösen."""
    _bereich_mit_seiten(client)
    for eingabe in ['"', "*", "NEAR(", "a OR b", "^foo"]:
        antwort = client.get("/api/search", params={"q": eingabe})
        assert antwort.status_code == 200


def test_index_folgt_der_bearbeitung(client: TestClient) -> None:
    space_id = _bereich_mit_seiten(client)
    seite = client.post(
        "/api/pages", json={"space_id": space_id, "title": "Kaffee", "body": "Alter Text"}
    ).json()

    client.patch(f"/api/pages/{seite['id']}", json={"body": "Espressomaschine entkalken"})
    assert client.get("/api/search", params={"q": "Espressomaschine"}).json() != []
    assert client.get("/api/search", params={"q": "Alter"}).json() == []


def test_geloeschte_seite_verschwindet_aus_dem_index(client: TestClient) -> None:
    space_id = _bereich_mit_seiten(client)
    seite = client.post(
        "/api/pages", json={"space_id": space_id, "title": "Provisorium", "body": "Wegwerftext"}
    ).json()
    assert client.get("/api/search", params={"q": "Wegwerftext"}).json() != []

    client.delete(f"/api/pages/{seite['id']}")
    assert client.get("/api/search", params={"q": "Wegwerftext"}).json() == []
