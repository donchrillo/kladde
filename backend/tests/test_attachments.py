"""Tests der Anhänge."""

from pathlib import Path

from fastapi.testclient import TestClient


def _seite(client: TestClient) -> int:
    space = client.post("/api/spaces", json={"name": "Handbuch"}).json()
    seite = client.post("/api/pages", json={"space_id": space["id"], "title": "Drucker"}).json()
    return int(seite["id"])


def _hochladen(client: TestClient, page_id: int, name: str = "anleitung.txt") -> dict:
    antwort = client.post(
        f"/api/pages/{page_id}/attachments",
        files={"file": (name, b"Inhalt der Datei", "text/plain")},
        data={"uploaded_by": "anna"},
    )
    assert antwort.status_code == 201, antwort.text
    return dict(antwort.json())


def test_upload_legt_datei_und_metadaten_an(client: TestClient, anhang_ablage: Path) -> None:
    page_id = _seite(client)
    anhang = _hochladen(client, page_id)

    assert anhang["filename"] == "anleitung.txt"
    assert anhang["size_bytes"] == len(b"Inhalt der Datei")
    assert anhang["uploaded_by"] == "anna"
    # Genau eine Datei auf der Platte, und ihr Name ist nicht der Originalname.
    dateien = list(anhang_ablage.iterdir())
    assert len(dateien) == 1
    assert dateien[0].name != "anleitung.txt"


def test_liste_und_download(client: TestClient) -> None:
    page_id = _seite(client)
    anhang = _hochladen(client, page_id)

    liste = client.get(f"/api/pages/{page_id}/attachments").json()
    assert [a["id"] for a in liste] == [anhang["id"]]

    download = client.get(f"/api/attachments/{anhang['id']}")
    assert download.status_code == 200
    assert download.content == b"Inhalt der Datei"


def test_pfad_im_dateinamen_wird_entschaerft(client: TestClient) -> None:
    """Ein präparierter Name darf das Ablageverzeichnis nicht verlassen."""
    page_id = _seite(client)
    anhang = _hochladen(client, page_id, name="../../etc/passwd")
    assert anhang["filename"] == "passwd"


def test_loeschen_entfernt_datei(client: TestClient, anhang_ablage: Path) -> None:
    page_id = _seite(client)
    anhang = _hochladen(client, page_id)

    assert client.delete(f"/api/attachments/{anhang['id']}").status_code == 204
    assert client.get(f"/api/attachments/{anhang['id']}").status_code == 404
    assert list(anhang_ablage.iterdir()) == []


def test_seite_loeschen_raeumt_anhaenge_auf(client: TestClient, anhang_ablage: Path) -> None:
    page_id = _seite(client)
    _hochladen(client, page_id)

    assert client.delete(f"/api/pages/{page_id}").status_code == 204
    assert list(anhang_ablage.iterdir()) == []


def test_upload_an_unbekannte_seite(client: TestClient) -> None:
    antwort = client.post(
        "/api/pages/999/attachments",
        files={"file": ("x.txt", b"x", "text/plain")},
    )
    assert antwort.status_code == 404


def test_zu_grosse_datei(client: TestClient, monkeypatch) -> None:
    from src.config import get_settings

    monkeypatch.setenv("MAX_UPLOAD_MB", "0")
    get_settings.cache_clear()

    page_id = _seite(client)
    antwort = client.post(
        f"/api/pages/{page_id}/attachments",
        files={"file": ("gross.bin", b"x" * 1024, "application/octet-stream")},
    )
    assert antwort.status_code == 413
    get_settings.cache_clear()


def test_download_liefert_fremde_typen_als_octet_stream(client: TestClient) -> None:
    """Der gemeldete Content-Type ist Eingabe, keine Tatsache.

    Eine hochgeladene HTML-Datei darf nicht als `text/html` aus derselben Origin
    zurückkommen wie das Wiki — sonst wäre sie eine Seite mit Zugriff auf die
    Sitzung, sobald jemand die Auslieferung einmal auf `inline` umstellt.
    """
    page_id = _seite(client)
    anhang = client.post(
        f"/api/pages/{page_id}/attachments",
        files={"file": ("boese.html", b"<script>alert(1)</script>", "text/html")},
    ).json()

    antwort = client.get(f"/api/attachments/{anhang['id']}")
    assert antwort.status_code == 200
    assert antwort.headers["content-type"] == "application/octet-stream"
    assert antwort.headers["x-content-type-options"] == "nosniff"


def test_download_behaelt_erlaubte_typen(client: TestClient) -> None:
    """Bilder und PDFs sollen weiter als das ankommen, was sie sind."""
    page_id = _seite(client)
    anhang = client.post(
        f"/api/pages/{page_id}/attachments",
        files={"file": ("bild.png", b"\x89PNG\r\n\x1a\n", "image/png")},
    ).json()

    antwort = client.get(f"/api/attachments/{anhang['id']}")
    assert antwort.headers["content-type"] == "image/png"
