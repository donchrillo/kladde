"""Bremse gegen Passwort-Raten und gegen Überlast am Login.

Zwei Dinge, die sich denselben Endpunkt teilen:

* **Rateversuche.** `POST /api/auth/login` war beliebig oft aufrufbar. Bei acht
  Zeichen Mindestpasswort ist Durchprobieren über VPN oder LAN in
  Reichweite. Nach ein paar Fehlversuchen wird deshalb gewartet, exponentiell
  wachsend.

* **Rechenlast.** Jede Prüfung rechnet scrypt (rund 16 MB Arbeitsspeicher) —
  auch für unbekannte Benutzernamen, absichtlich, damit sich an der Antwortzeit
  nicht ablesen lässt, welche Konten existieren. Genau das ist aber ein Hebel:
  ein einziger Client mit ein paar hundert parallelen Anfragen belegte damit
  Gigabytes. Also nur eine Handvoll Prüfungen gleichzeitig.

Der Zustand liegt im Prozess, nicht in der Datenbank. Für ein internes Wiki mit
einem einzigen Backend-Prozess reicht das; ein Neustart vergisst die Sperren,
was hier eher Vorteil als Nachteil ist.
"""

import threading
import time
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass

from fastapi import HTTPException, Request, status

# So viele Fehlversuche sind frei, danach beginnt die Wartezeit.
FREIVERSUCHE = 5
# Wartezeit nach dem ersten Fehlversuch jenseits der Freigrenze; verdoppelt sich
# mit jedem weiteren (2, 4, 8, ... Sekunden) bis `MAX_WARTE`.
BASIS_WARTE = 2.0
MAX_WARTE = 15 * 60.0
# Einträge, die so lange still sind, werden vergessen — sonst wüchse die Tabelle
# mit jedem je gescheiterten Benutzernamen.
VERFALL = 60 * 60.0
# Gleichzeitig laufende scrypt-Berechnungen.
GLEICHZEITIGE_PRUEFUNGEN = 4
# So lange wartet eine Anfrage auf einen freien Rechenplatz, bevor sie aufgibt.
WARTE_AUF_PLATZ = 10.0


@dataclass
class _Eintrag:
    fehlversuche: int = 0
    frei_ab: float = 0.0
    zuletzt: float = 0.0


_sperre = threading.Lock()
_eintraege: dict[tuple[str, str], _Eintrag] = {}
_rechenplaetze = threading.BoundedSemaphore(GLEICHZEITIGE_PRUEFUNGEN)


def absender(request: Request) -> str:
    """Die IP des Anfragenden, so gut sie sich feststellen lässt.

    Hinter Caddy kommt jede Anfrage von 127.0.0.1; die echte Adresse steht in
    `X-Forwarded-For`. Genommen wird der **letzte** Eintrag: ein Angreifer kann
    den Header vorne beliebig auffüllen, der Proxy hängt die tatsächliche
    Gegenstelle hinten an.
    """
    weitergereicht = request.headers.get("x-forwarded-for")
    if weitergereicht:
        teile = [t.strip() for t in weitergereicht.split(",") if t.strip()]
        if teile:
            return teile[-1]
    return request.client.host if request.client else "unbekannt"


def _schluessel(request: Request, username: str) -> tuple[str, str]:
    return (absender(request), username.strip().lower())


def _aufraeumen(jetzt: float) -> None:
    """Alte Einträge wegwerfen. Läuft unter `_sperre`."""
    for schluessel in [k for k, e in _eintraege.items() if jetzt - e.zuletzt > VERFALL]:
        del _eintraege[schluessel]


def pruefen(request: Request, username: str) -> None:
    """Wirft 429, solange dieser Absender für dieses Konto gesperrt ist."""
    jetzt = time.monotonic()
    with _sperre:
        _aufraeumen(jetzt)
        eintrag = _eintraege.get(_schluessel(request, username))
        rest = 0.0 if eintrag is None else eintrag.frei_ab - jetzt
    if rest > 0:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=(
                f"Zu viele Fehlversuche — bitte {int(rest) + 1} Sekunden warten "
                "und es dann erneut versuchen"
            ),
            headers={"Retry-After": str(int(rest) + 1)},
        )


def fehlschlag(request: Request, username: str) -> None:
    """Vermerkt einen gescheiterten Versuch und setzt ggf. die Sperre."""
    jetzt = time.monotonic()
    with _sperre:
        eintrag = _eintraege.setdefault(_schluessel(request, username), _Eintrag())
        eintrag.fehlversuche += 1
        eintrag.zuletzt = jetzt
        ueberzaehlig = eintrag.fehlversuche - FREIVERSUCHE
        if ueberzaehlig > 0:
            warte = min(BASIS_WARTE * 2 ** (ueberzaehlig - 1), MAX_WARTE)
            eintrag.frei_ab = jetzt + warte


def erfolg(request: Request, username: str) -> None:
    """Löscht den Zähler nach einer geglückten Anmeldung."""
    with _sperre:
        _eintraege.pop(_schluessel(request, username), None)


@contextmanager
def rechenplatz() -> Iterator[None]:
    """Begrenzt, wie viele Passwortprüfungen gleichzeitig rechnen dürfen."""
    if not _rechenplaetze.acquire(timeout=WARTE_AUF_PLATZ):
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Gerade zu viele Anmeldeversuche — bitte gleich noch einmal versuchen",
            headers={"Retry-After": "5"},
        )
    try:
        yield
    finally:
        _rechenplaetze.release()


def zuruecksetzen() -> None:
    """Vergisst alle Zähler und Sperren. Für Tests."""
    with _sperre:
        _eintraege.clear()
