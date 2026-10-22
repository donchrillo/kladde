"""
Kladde — FastAPI-Backend.

Stellt die REST-API bereit (SQLAlchemy + Alembic) und liefert in Produktion das
gebaute PWA-Frontend aus. Hinter Caddy unter ``https://pn40.local``.
"""

import logging
from collections.abc import Awaitable, Callable
from pathlib import Path

from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from .config import get_settings
from .routers import attachments, auth, health, overview, pages, search, spaces, users

settings = get_settings()

app = FastAPI(title="Kladde backend")

# Offener Betrieb ist ein Ausnahmezustand, kein Normalfall: er macht jeden
# Besucher zum Administrator. Wer ihn einschaltet, soll ihn im Journal sehen.
if not settings.auth_enabled:
    logging.getLogger("uvicorn.error").warning(
        "AUTH_ENABLED=false — das Wiki läuft OHNE Anmeldung: jeder Zugriff hat "
        "Administratorrechte, private Bereiche sind nicht geschützt."
    )

# CORS: nur die Produktions-Origin. Im Dev wird sie gar nicht gebraucht — der
# Vite-Server proxyt `/api` ans Backend, die PWA spricht also immer same-origin.
# Früher stand hier zusätzlich `http://(localhost|127.0.0.1):<port>` als Regex;
# zusammen mit `allow_credentials` durfte damit jede lokal laufende Software
# credential-behaftete Antworten des Wikis lesen.
app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.frontend_url],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def kein_mimetype_raten(
    request: Request, call_next: Callable[[Request], Awaitable[Response]]
) -> Response:
    """`nosniff` auf jeder Antwort.

    Anhänge werden mit dem Content-Type ausgeliefert, den der Uploader gemeldet
    hat. Sie liegen same-origin zum Wiki — ohne diesen Header entschiede im
    Zweifel der Browser, was er in einer Datei zu sehen glaubt.
    """
    antwort = await call_next(request)
    antwort.headers.setdefault("X-Content-Type-Options", "nosniff")
    return antwort


app.include_router(health.router, prefix="/api")
app.include_router(auth.router, prefix="/api/auth", tags=["auth"])
app.include_router(spaces.router, prefix="/api/spaces", tags=["spaces"])
app.include_router(pages.router, prefix="/api/pages", tags=["pages"])
app.include_router(search.router, prefix="/api/search", tags=["search"])
# Startseiten-Daten: /api/recent, /api/labels
app.include_router(overview.router, prefix="/api", tags=["overview"])
app.include_router(users.router, prefix="/api/users", tags=["users"])
# Anhänge hängen an zwei Pfaden (/pages/{id}/attachments und /attachments/{id})
# und bringen ihre Präfixe daher selbst mit.
app.include_router(attachments.router, prefix="/api", tags=["attachments"])

# In Produktion liegt hier das gebaute Frontend. Nur mounten, wenn vorhanden.
_frontend_dist = Path(__file__).resolve().parents[2] / "frontend" / "dist"
if _frontend_dist.is_dir():
    app.mount("/", StaticFiles(directory=_frontend_dist, html=True), name="frontend")
