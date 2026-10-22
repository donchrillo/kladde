"""Tests für Bereiche und den Seitenbaum."""

from fastapi.testclient import TestClient


def test_list_spaces_empty(client: TestClient) -> None:
    res = client.get("/api/spaces")
    assert res.status_code == 200
    assert res.json() == []


def test_create_space_leitet_key_aus_name_ab(client: TestClient) -> None:
    res = client.post("/api/spaces", json={"name": "IT & Büro"})
    assert res.status_code == 201
    assert res.json()["key"] == "it-buero"


def test_create_space_mit_doppeltem_key_gibt_409(client: TestClient) -> None:
    client.post("/api/spaces", json={"name": "IT"})
    res = client.post("/api/spaces", json={"name": "IT"})
    assert res.status_code == 409


def test_get_unbekannter_space_gibt_404(client: TestClient) -> None:
    assert client.get("/api/spaces/gibtsnicht").status_code == 404


def test_seitenbaum_ist_verschachtelt(client: TestClient) -> None:
    space = client.post("/api/spaces", json={"name": "Handbuch"}).json()
    wurzel = client.post("/api/pages", json={"space_id": space["id"], "title": "Einstieg"}).json()
    client.post(
        "/api/pages",
        json={"space_id": space["id"], "title": "Installation", "parent_id": wurzel["id"]},
    )

    res = client.get(f"/api/spaces/{space['key']}/pages")
    assert res.status_code == 200
    baum = res.json()
    assert len(baum) == 1
    assert baum[0]["title"] == "Einstieg"
    assert [k["title"] for k in baum[0]["children"]] == ["Installation"]


# ── Löschen ─────────────────────────────────────────────────────────────────


def test_leeren_bereich_loeschen(client: TestClient) -> None:
    space = client.post("/api/spaces", json={"name": "Leer"}).json()
    assert client.delete(f"/api/spaces/{space['key']}").status_code == 204
    assert client.get(f"/api/spaces/{space['key']}").status_code == 404


def test_bereich_mit_seiten_gibt_409(client: TestClient) -> None:
    space = client.post("/api/spaces", json={"name": "Voll"}).json()
    client.post("/api/pages", json={"space_id": space["id"], "title": "Einstieg"})

    antwort = client.delete(f"/api/spaces/{space['key']}")
    assert antwort.status_code == 409
    # Die Meldung nennt die Zahl, damit im Browser klar ist, was noch im Weg ist.
    assert "1 Seite" in antwort.json()["detail"]
    # Der Bereich muss den abgelehnten Versuch unbeschadet überstehen.
    assert client.get(f"/api/spaces/{space['key']}").status_code == 200


def test_bereich_loeschen_geht_nach_dem_ausraeumen(client: TestClient) -> None:
    """Erst die Seiten weg, dann der Bereich — so ist die Reihenfolge gedacht."""
    space = client.post("/api/spaces", json={"name": "Voll"}).json()
    wurzel = client.post("/api/pages", json={"space_id": space["id"], "title": "Oben"}).json()
    kind = client.post(
        "/api/pages",
        json={"space_id": space["id"], "title": "Unten", "parent_id": wurzel["id"]},
    ).json()

    # Auch eine einzelne Seite mit Unterseiten bleibt geschützt.
    assert client.delete(f"/api/pages/{wurzel['id']}").status_code == 409

    assert client.delete(f"/api/pages/{kind['id']}").status_code == 204
    assert client.delete(f"/api/pages/{wurzel['id']}").status_code == 204
    assert client.delete(f"/api/spaces/{space['key']}").status_code == 204
    assert client.get(f"/api/spaces/{space['key']}").status_code == 404


def test_patch_laesst_nicht_mitgeschicktes_in_ruhe(client: TestClient) -> None:
    """Ein PATCH nur mit `name` darf die Beschreibung nicht löschen."""
    space = client.post("/api/spaces", json={"name": "IT", "description": "Alles zur IT"}).json()

    umbenannt = client.patch(f"/api/spaces/{space['key']}", json={"name": "IT-Büro"})
    assert umbenannt.status_code == 200
    assert umbenannt.json()["name"] == "IT-Büro"
    assert umbenannt.json()["description"] == "Alles zur IT"

    # Ausdrücklich auf null setzen geht weiterhin.
    geleert = client.patch(f"/api/spaces/{space['key']}", json={"description": None})
    assert geleert.json()["description"] is None
    assert geleert.json()["name"] == "IT-Büro"


def test_schluessel_bleibt_auch_wenn_einer_geschickt_wird(client: TestClient) -> None:
    """`key` ist kein Feld von PATCH — Links sollen halten, nicht brechen."""
    space = client.post("/api/spaces", json={"name": "IT"}).json()
    geaendert = client.patch(f"/api/spaces/{space['key']}", json={"key": "anders"})
    assert geaendert.status_code == 200
    assert geaendert.json()["key"] == space["key"]


def test_bereichsliste_nennt_das_eigene_recht(client: TestClient) -> None:
    """Damit die Oberfläche gar nicht erst anbietet, was im 403 endet."""
    client.post("/api/spaces", json={"name": "IT"})
    # Im offenen Betrieb ist jeder Administrator: volle Stufe überall.
    assert [s["mein_recht"] for s in client.get("/api/spaces").json()] == ["verwalten"]
