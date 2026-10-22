"""API für Anhänge an Seiten.

Upload läuft über `POST /api/pages/{page_id}/attachments`, Download und Löschen
über `/api/attachments/{id}`. Die Datei liegt unter `ATTACHMENT_DIR` unter einem
UUID-Namen; der Originalname steht nur in der Datenbank.
"""

import uuid
from pathlib import Path

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from fastapi.responses import FileResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..auth import Principal, get_principal, pruefe_bereich
from ..config import get_settings
from ..database import get_db
from ..models import Attachment, Page, Recht
from ..schemas import AttachmentRead

router = APIRouter()


def _ablage() -> Path:
    """Das Verzeichnis für Anhänge; wird bei Bedarf angelegt."""
    ordner = Path(get_settings().attachment_dir)
    ordner.mkdir(parents=True, exist_ok=True)
    return ordner


def _seite_holen(page_id: int, db: Session) -> Page:
    seite = db.get(Page, page_id)
    if seite is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Seite nicht gefunden")
    return seite


def _anhang_holen(attachment_id: int, db: Session) -> Attachment:
    anhang = db.get(Attachment, attachment_id)
    if anhang is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Anhang nicht gefunden")
    return anhang


# Content-Types, die wir so ausliefern, wie sie gemeldet wurden. Alles andere
# geht als `application/octet-stream` raus.
#
# Der Wert stammt aus dem Multipart-Header des Uploaders, ist also Eingabe und
# keine Tatsache. Zusammen mit `Content-Disposition: attachment` (setzt
# `FileResponse` über `filename`) und dem `nosniff` aus `main.py` bliebe eine
# hochgeladene HTML-Datei zwar harmlos — aber die Allowlist ist die Stelle, die
# hält, wenn jemand später auf `inline` umstellt, damit PDFs im Browser aufgehen.
ERLAUBTE_TYPEN = frozenset(
    {
        "image/png",
        "image/jpeg",
        "image/gif",
        "image/webp",
        "image/avif",
        "image/bmp",
        "image/tiff",
        "application/pdf",
        "text/plain",
        "text/csv",
    }
)


def _ausliefer_typ(gemeldet: str) -> str:
    """Der Content-Type, mit dem ein Anhang das Haus verlässt."""
    return (
        gemeldet
        if gemeldet.split(";")[0].strip().lower() in ERLAUBTE_TYPEN
        else ("application/octet-stream")
    )


def _sicherer_anzeigename(name: str | None) -> str:
    """Reduziert den hochgeladenen Namen auf den reinen Dateinamen.

    Der Name landet nie im Dateisystempfad (dort steht die UUID), aber er wird
    im Content-Disposition-Header ausgeliefert — Pfadanteile und Zeilenumbrüche
    haben darin nichts verloren.
    """
    roh = (name or "datei").replace("\\", "/").split("/")[-1]
    sauber = "".join(z for z in roh if z.isprintable() and z not in '"\r\n').strip()
    return sauber or "datei"


@router.get("/pages/{page_id}/attachments", response_model=list[AttachmentRead])
def list_attachments(
    page_id: int,
    db: Session = Depends(get_db),
    principal: Principal = Depends(get_principal),
) -> list[Attachment]:
    seite = _seite_holen(page_id, db)
    pruefe_bereich(principal, seite.space_id, Recht.LESEN, db)
    return list(
        db.scalars(
            select(Attachment).where(Attachment.page_id == page_id).order_by(Attachment.created_at)
        )
    )


@router.post(
    "/pages/{page_id}/attachments",
    response_model=AttachmentRead,
    status_code=status.HTTP_201_CREATED,
)
def upload_attachment(
    page_id: int,
    datei: UploadFile = File(..., alias="file"),
    uploaded_by: str | None = Form(default=None),
    db: Session = Depends(get_db),
    principal: Principal = Depends(get_principal),
) -> Attachment:
    seite = _seite_holen(page_id, db)
    pruefe_bereich(principal, seite.space_id, Recht.SCHREIBEN, db)

    grenze = get_settings().max_upload_mb * 1024 * 1024
    stored_name = uuid.uuid4().hex
    ziel = _ablage() / stored_name

    # Streamend schreiben und dabei mitzählen: eine zu große Datei soll nicht
    # erst vollständig im Speicher landen.
    groesse = 0
    try:
        with ziel.open("wb") as ausgabe:
            while stueck := datei.file.read(1024 * 1024):
                groesse += len(stueck)
                if groesse > grenze:
                    raise HTTPException(
                        status_code=status.HTTP_413_CONTENT_TOO_LARGE,
                        detail=f"Datei überschreitet {get_settings().max_upload_mb} MB",
                    )
                ausgabe.write(stueck)
    except Exception:
        ziel.unlink(missing_ok=True)
        raise

    anhang = Attachment(
        page_id=page_id,
        filename=_sicherer_anzeigename(datei.filename),
        stored_name=stored_name,
        content_type=datei.content_type or "application/octet-stream",
        size_bytes=groesse,
        # Angemeldet gewinnt der Anzeigename; offen bleibt der gemeldete Wert.
        uploaded_by=(principal.display_name if principal.user_id is not None else uploaded_by),
    )
    db.add(anhang)
    db.commit()
    db.refresh(anhang)
    return anhang


@router.get("/attachments/{attachment_id}")
def download_attachment(
    attachment_id: int,
    db: Session = Depends(get_db),
    principal: Principal = Depends(get_principal),
) -> FileResponse:
    anhang = _anhang_holen(attachment_id, db)
    seite = _seite_holen(anhang.page_id, db)
    pruefe_bereich(principal, seite.space_id, Recht.LESEN, db)

    pfad = _ablage() / anhang.stored_name
    if not pfad.is_file():
        raise HTTPException(status_code=status.HTTP_410_GONE, detail="Datei fehlt auf dem Server")
    return FileResponse(
        pfad,
        media_type=_ausliefer_typ(anhang.content_type),
        filename=anhang.filename,
    )


@router.delete("/attachments/{attachment_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_attachment(
    attachment_id: int,
    db: Session = Depends(get_db),
    principal: Principal = Depends(get_principal),
) -> None:
    anhang = _anhang_holen(attachment_id, db)
    seite = _seite_holen(anhang.page_id, db)
    pruefe_bereich(principal, seite.space_id, Recht.LOESCHEN, db)

    (_ablage() / anhang.stored_name).unlink(missing_ok=True)
    db.delete(anhang)
    db.commit()


def dateien_loeschen(anhaenge: list[Attachment]) -> None:
    """Löscht die Dateien zu Anhängen von der Platte.

    Wird beim Löschen einer Seite gebraucht: die DB-Zeilen verschwinden per
    Cascade, die Dateien muss jemand aufräumen.
    """
    ordner = _ablage()
    for anhang in anhaenge:
        (ordner / anhang.stored_name).unlink(missing_ok=True)
