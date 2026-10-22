"""Tests für Seiten, Hierarchie und Versionierung."""

import pytest
from fastapi.testclient import TestClient
from src.routers.pages import MAX_TIEFE


@pytest.fixture
def space_id(client: TestClient) -> int:
    res = client.post("/api/spaces", json={"name": "Handbuch"})
    return int(res.json()["id"])


def test_create_page_legt_revision_1_an(client: TestClient, space_id: int) -> None:
    res = client.post(
        "/api/pages",
        json={"space_id": space_id, "title": "Einstieg", "body": "# Hallo", "author": "anna"},
    )
    assert res.status_code == 201
    seite = res.json()
    assert seite["slug"] == "einstieg"

    versionen = client.get(f"/api/pages/{seite['id']}/versions").json()
    assert [v["revision"] for v in versionen] == [1]
    assert versionen[0]["author"] == "anna"


def test_doppelter_titel_bekommt_eindeutigen_slug(client: TestClient, space_id: int) -> None:
    client.post("/api/pages", json={"space_id": space_id, "title": "Einstieg"})
    zweite = client.post("/api/pages", json={"space_id": space_id, "title": "Einstieg"}).json()
    assert zweite["slug"] == "einstieg-2"


def test_update_haengt_neue_revision_an(client: TestClient, space_id: int) -> None:
    seite = client.post(
        "/api/pages", json={"space_id": space_id, "title": "Einstieg", "body": "alt"}
    ).json()

    res = client.patch(f"/api/pages/{seite['id']}", json={"body": "neu"})
    assert res.status_code == 200
    assert res.json()["body"] == "neu"

    versionen = client.get(f"/api/pages/{seite['id']}/versions").json()
    assert [v["revision"] for v in versionen] == [2, 1]  # neueste zuerst

    alt = client.get(f"/api/pages/{seite['id']}/versions/1").json()
    assert alt["body"] == "alt"


def test_reines_verschieben_erzeugt_keine_revision(client: TestClient, space_id: int) -> None:
    eltern = client.post("/api/pages", json={"space_id": space_id, "title": "Oben"}).json()
    kind = client.post("/api/pages", json={"space_id": space_id, "title": "Unten"}).json()

    client.patch(f"/api/pages/{kind['id']}", json={"parent_id": eltern["id"]})

    versionen = client.get(f"/api/pages/{kind['id']}/versions").json()
    assert [v["revision"] for v in versionen] == [1]


def test_seite_kann_nicht_unter_eigene_unterseite(client: TestClient, space_id: int) -> None:
    eltern = client.post("/api/pages", json={"space_id": space_id, "title": "Oben"}).json()
    kind = client.post(
        "/api/pages", json={"space_id": space_id, "title": "Unten", "parent_id": eltern["id"]}
    ).json()

    res = client.patch(f"/api/pages/{eltern['id']}", json={"parent_id": kind["id"]})
    assert res.status_code == 400


def test_seite_mit_unterseiten_loeschen_gibt_409(client: TestClient, space_id: int) -> None:
    eltern = client.post("/api/pages", json={"space_id": space_id, "title": "Oben"}).json()
    client.post(
        "/api/pages", json={"space_id": space_id, "title": "Unten", "parent_id": eltern["id"]}
    )

    assert client.delete(f"/api/pages/{eltern['id']}").status_code == 409


def test_blatt_loeschen_entfernt_auch_die_revisionen(client: TestClient, space_id: int) -> None:
    seite = client.post("/api/pages", json={"space_id": space_id, "title": "Weg"}).json()

    assert client.delete(f"/api/pages/{seite['id']}").status_code == 204
    assert client.get(f"/api/pages/{seite['id']}").status_code == 404
    assert client.get(f"/api/pages/{seite['id']}/versions").status_code == 404


def test_page_in_unbekanntem_space_gibt_404(client: TestClient) -> None:
    res = client.post("/api/pages", json={"space_id": 999, "title": "Waise"})
    assert res.status_code == 404


# ── Ebenenbegrenzung ────────────────────────────────────────────────────────


def _kette(client: TestClient, space_id: int, tiefe: int) -> list[dict]:
    """Legt `tiefe` ineinander verschachtelte Seiten an und gibt sie zurück."""
    seiten: list[dict] = []
    parent: int | None = None
    for stufe in range(tiefe):
        antwort = client.post(
            "/api/pages",
            json={"space_id": space_id, "title": f"Ebene {stufe + 1}", "parent_id": parent},
        )
        assert antwort.status_code == 201, antwort.text
        seiten.append(antwort.json())
        parent = antwort.json()["id"]
    return seiten


def test_erlaubte_tiefe_wird_angelegt(client: TestClient) -> None:
    space = client.post("/api/spaces", json={"name": "Handbuch"}).json()
    assert len(_kette(client, space["id"], MAX_TIEFE)) == MAX_TIEFE


def test_eine_ebene_zu_tief_wird_abgelehnt(client: TestClient) -> None:
    space = client.post("/api/spaces", json={"name": "Handbuch"}).json()
    seiten = _kette(client, space["id"], MAX_TIEFE)

    antwort = client.post(
        "/api/pages",
        json={"space_id": space["id"], "title": "Zu tief", "parent_id": seiten[-1]["id"]},
    )
    assert antwort.status_code == 400
    assert "Ebenen" in antwort.json()["detail"]


def test_verschieben_beachtet_die_unterseiten(client: TestClient) -> None:
    """Ein zweistufiger Ast darf nicht ganz nach unten wandern — die Kinder lägen zu tief."""
    space = client.post("/api/spaces", json={"name": "Handbuch"}).json()
    ebenen = _kette(client, space["id"], MAX_TIEFE - 1)

    # Separater Ast mit eigener Unterseite.
    ast = client.post("/api/pages", json={"space_id": space["id"], "title": "Ast"}).json()
    client.post(
        "/api/pages",
        json={"space_id": space["id"], "title": "Ast-Kind", "parent_id": ast["id"]},
    )

    antwort = client.patch(f"/api/pages/{ast['id']}", json={"parent_id": ebenen[-1]["id"]})
    assert antwort.status_code == 400

    # Ohne Unterseite ginge derselbe Zug.
    blatt = client.post("/api/pages", json={"space_id": space["id"], "title": "Blatt"}).json()
    assert (
        client.patch(f"/api/pages/{blatt['id']}", json={"parent_id": ebenen[-1]["id"]}).status_code
        == 200
    )


# ── Bereichswechsel ─────────────────────────────────────────────────────────


def test_bereichswechsel_nimmt_den_ganzen_ast_mit(client: TestClient) -> None:
    quelle = client.post("/api/spaces", json={"name": "Quelle"}).json()
    ziel = client.post("/api/spaces", json={"name": "Ziel"}).json()
    oben = client.post("/api/pages", json={"space_id": quelle["id"], "title": "Oben"}).json()
    unten = client.post(
        "/api/pages", json={"space_id": quelle["id"], "title": "Unten", "parent_id": oben["id"]}
    ).json()

    antwort = client.patch(f"/api/pages/{oben['id']}", json={"space_id": ziel["id"]})
    assert antwort.status_code == 200, antwort.text
    assert antwort.json()["space_id"] == ziel["id"]
    assert antwort.json()["parent_id"] is None
    # Die Unterseite darf nicht im alten Bereich zurückbleiben.
    assert client.get(f"/api/pages/{unten['id']}").json()["space_id"] == ziel["id"]
    assert client.get(f"/api/spaces/{quelle['key']}/pages").json() == []


def test_bereichswechsel_vergibt_freien_slug(client: TestClient) -> None:
    """Im Zielbereich kann derselbe Slug schon belegt sein."""
    quelle = client.post("/api/spaces", json={"name": "Quelle"}).json()
    ziel = client.post("/api/spaces", json={"name": "Ziel"}).json()
    client.post("/api/pages", json={"space_id": ziel["id"], "title": "Einstieg"})
    wandert = client.post("/api/pages", json={"space_id": quelle["id"], "title": "Einstieg"}).json()
    assert wandert["slug"] == "einstieg"

    antwort = client.patch(f"/api/pages/{wandert['id']}", json={"space_id": ziel["id"]})
    assert antwort.json()["slug"] == "einstieg-2"


def test_bereichswechsel_schreibt_verweise_um(client: TestClient) -> None:
    """Interne Links tragen den Bereichsschlüssel im Text und müssen mitziehen."""
    quelle = client.post("/api/spaces", json={"name": "Quelle"}).json()
    ziel = client.post("/api/spaces", json={"name": "Ziel"}).json()
    wandert = client.post("/api/pages", json={"space_id": quelle["id"], "title": "Wanderer"}).json()
    verweiser = client.post(
        "/api/pages",
        json={
            "space_id": quelle["id"],
            "title": "Verweiser",
            "body": "Siehe [Wanderer](/wiki/quelle/wanderer).",
        },
    ).json()
    # Rückverweis steht, bevor verschoben wird.
    assert [v["id"] for v in client.get(f"/api/pages/{wandert['id']}/backlinks").json()] == [
        verweiser["id"]
    ]

    client.patch(f"/api/pages/{wandert['id']}", json={"space_id": ziel["id"]})

    body = client.get(f"/api/pages/{verweiser['id']}").json()["body"]
    assert "/wiki/ziel/wanderer" in body
    assert "/wiki/quelle/wanderer" not in body
    # Und der Rückverweis überlebt den Umzug.
    assert [v["id"] for v in client.get(f"/api/pages/{wandert['id']}/backlinks").json()] == [
        verweiser["id"]
    ]


def test_bereichswechsel_erlaubt_elternteil_im_zielbereich(client: TestClient) -> None:
    quelle = client.post("/api/spaces", json={"name": "Quelle"}).json()
    ziel = client.post("/api/spaces", json={"name": "Ziel"}).json()
    dach = client.post("/api/pages", json={"space_id": ziel["id"], "title": "Dach"}).json()
    wandert = client.post("/api/pages", json={"space_id": quelle["id"], "title": "Wanderer"}).json()

    antwort = client.patch(
        f"/api/pages/{wandert['id']}",
        json={"space_id": ziel["id"], "parent_id": dach["id"]},
    )
    assert antwort.status_code == 200, antwort.text
    assert antwort.json()["parent_id"] == dach["id"]


def test_bereichswechsel_lehnt_fremden_elternteil_ab(client: TestClient) -> None:
    """Der neue Elternteil muss im Zielbereich liegen, nicht irgendwo."""
    quelle = client.post("/api/spaces", json={"name": "Quelle"}).json()
    ziel = client.post("/api/spaces", json={"name": "Ziel"}).json()
    drittes = client.post("/api/spaces", json={"name": "Drittes"}).json()
    fremd = client.post("/api/pages", json={"space_id": drittes["id"], "title": "Fremd"}).json()
    wandert = client.post("/api/pages", json={"space_id": quelle["id"], "title": "Wanderer"}).json()

    antwort = client.patch(
        f"/api/pages/{wandert['id']}",
        json={"space_id": ziel["id"], "parent_id": fremd["id"]},
    )
    assert antwort.status_code == 400
    assert "Bereich" in antwort.json()["detail"]
    assert client.get(f"/api/pages/{wandert['id']}").json()["space_id"] == quelle["id"]


def test_bereichswechsel_beachtet_die_ebenengrenze(client: TestClient) -> None:
    quelle = client.post("/api/spaces", json={"name": "Quelle"}).json()
    ziel = client.post("/api/spaces", json={"name": "Ziel"}).json()
    tief = _kette(client, ziel["id"], MAX_TIEFE)
    # Ein zweistufiger Ast passt nicht mehr unter die unterste Ebene.
    oben = client.post("/api/pages", json={"space_id": quelle["id"], "title": "Oben"}).json()
    client.post(
        "/api/pages", json={"space_id": quelle["id"], "title": "Unten", "parent_id": oben["id"]}
    )

    antwort = client.patch(
        f"/api/pages/{oben['id']}",
        json={"space_id": ziel["id"], "parent_id": tief[-1]["id"]},
    )
    assert antwort.status_code == 400
    assert "Ebenen" in antwort.json()["detail"]


def test_bereichswechsel_haelt_die_suche_aktuell(client: TestClient) -> None:
    quelle = client.post("/api/spaces", json={"name": "Quelle"}).json()
    ziel = client.post("/api/spaces", json={"name": "Ziel"}).json()
    wandert = client.post(
        "/api/pages",
        json={"space_id": quelle["id"], "title": "Wanderer", "body": "Zauberwort Kaltluftschneise"},
    ).json()

    client.patch(f"/api/pages/{wandert['id']}", json={"space_id": ziel["id"]})

    treffer = client.get("/api/search?q=Kaltluftschneise").json()
    assert len(treffer) == 1
    assert treffer[0]["space_key"] == ziel["key"]


# ── Reihenfolge ─────────────────────────────────────────────────────────────


def _titel_der_ebene(client: TestClient, parent_id: int | None = None) -> list[str]:
    """Titel einer Ebene in Baumreihenfolge, samt Prüfung auf lückenlose Positionen."""
    baum = client.get("/api/spaces/handbuch/pages").json()
    ebene = baum
    if parent_id is not None:
        ebene = next(k for k in baum if k["id"] == parent_id)["children"]
    assert [k["position"] for k in ebene] == list(range(len(ebene)))
    return [k["title"] for k in ebene]


def _seiten(
    client: TestClient, space_id: int, *titel: str, parent_id: int | None = None
) -> list[int]:
    return [
        client.post(
            "/api/pages", json={"space_id": space_id, "title": t, "parent_id": parent_id}
        ).json()["id"]
        for t in titel
    ]


def test_position_setzen_nummeriert_geschwister_neu(client: TestClient, space_id: int) -> None:
    a, b, c, d = _seiten(client, space_id, "A", "B", "C", "D")

    client.patch(f"/api/pages/{d}", json={"position": 0})
    assert _titel_der_ebene(client) == ["D", "A", "B", "C"]

    client.patch(f"/api/pages/{d}", json={"position": 2})
    assert _titel_der_ebene(client) == ["A", "B", "D", "C"]


def test_position_ausserhalb_wird_geklemmt(client: TestClient, space_id: int) -> None:
    a, b, c = _seiten(client, space_id, "A", "B", "C")

    client.patch(f"/api/pages/{a}", json={"position": 99})
    assert _titel_der_ebene(client) == ["B", "C", "A"]

    client.patch(f"/api/pages/{a}", json={"position": -5})
    assert _titel_der_ebene(client) == ["A", "B", "C"]


def test_umsortieren_erzeugt_keine_revision(client: TestClient, space_id: int) -> None:
    a, b = _seiten(client, space_id, "A", "B")
    client.patch(f"/api/pages/{b}", json={"position": 0})
    assert len(client.get(f"/api/pages/{b}/versions").json()) == 1


def test_umhaengen_setzt_seite_ans_ende(client: TestClient, space_id: int) -> None:
    (eltern,) = _seiten(client, space_id, "Eltern")
    _seiten(client, space_id, "X", "Y", parent_id=eltern)
    # Auf der obersten Ebene steht "Neu" an zweiter Stelle — diese Nummer darf
    # es nicht mitnehmen.
    (neu,) = _seiten(client, space_id, "Neu")

    client.patch(f"/api/pages/{neu}", json={"parent_id": eltern})
    assert _titel_der_ebene(client, eltern) == ["X", "Y", "Neu"]


def test_umhaengen_mit_position(client: TestClient, space_id: int) -> None:
    (eltern,) = _seiten(client, space_id, "Eltern")
    _seiten(client, space_id, "X", "Y", parent_id=eltern)
    (neu,) = _seiten(client, space_id, "Neu")

    client.patch(f"/api/pages/{neu}", json={"parent_id": eltern, "position": 0})
    assert _titel_der_ebene(client, eltern) == ["Neu", "X", "Y"]
