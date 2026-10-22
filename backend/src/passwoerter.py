"""Passwörter hashen und prüfen.

Bewusst `hashlib.scrypt` aus der Standardbibliothek statt einer zusätzlichen
Abhängigkeit (argon2, bcrypt): scrypt ist speicherhart, in CPython in C
implementiert und für ein internes Wiki mit einer Handvoll Konten mehr als
ausreichend.

Der gespeicherte String trägt die Parameter mit sich:

    scrypt$16384$8$1$<salt_base64>$<hash_base64>

Dadurch lassen sich die Kosten später erhöhen, ohne Bestandshashes zu brechen —
alte Hashes werden weiterhin mit ihren eigenen Parametern geprüft.
"""

import base64
import hashlib
import hmac
import secrets

# Kosten. n muss eine Zweierpotenz sein; 2**14 braucht rund 16 MB und liegt
# im Bereich weniger Millisekunden — für eine Anmeldung unmerklich.
_N = 2**14
_R = 8
_P = 1
_DKLEN = 32
_SALT_BYTES = 16

_PREFIX = "scrypt"


def _ableiten(passwort: str, salt: bytes, n: int, r: int, p: int) -> bytes:
    return hashlib.scrypt(passwort.encode("utf-8"), salt=salt, n=n, r=r, p=p, dklen=_DKLEN)


def _b64(rohdaten: bytes) -> str:
    return base64.b64encode(rohdaten).decode("ascii")


def hash_erzeugen(passwort: str) -> str:
    """Erzeugt den zu speichernden Hash-String für ein Klartext-Passwort."""
    salt = secrets.token_bytes(_SALT_BYTES)
    abgeleitet = _ableiten(passwort, salt, _N, _R, _P)
    return f"{_PREFIX}${_N}${_R}${_P}${_b64(salt)}${_b64(abgeleitet)}"


def hash_pruefen(passwort: str, gespeichert: str | None) -> bool:
    """Prüft ein Klartext-Passwort gegen den gespeicherten Hash.

    Fehlt der Hash oder ist er unlesbar, wird trotzdem gerechnet und `False`
    zurückgegeben: sonst ließe sich an der Antwortzeit ablesen, ob ein Konto
    überhaupt existiert.
    """
    if not gespeichert:
        _ableiten(passwort, b"dummy-salt-16byt", _N, _R, _P)
        return False

    teile = gespeichert.split("$")
    if len(teile) != 6 or teile[0] != _PREFIX:
        _ableiten(passwort, b"dummy-salt-16byt", _N, _R, _P)
        return False

    try:
        n, r, p = int(teile[1]), int(teile[2]), int(teile[3])
        salt = base64.b64decode(teile[4])
        erwartet = base64.b64decode(teile[5])
        errechnet = _ableiten(passwort, salt, n, r, p)
    except (ValueError, TypeError):
        return False

    return hmac.compare_digest(errechnet, erwartet)


def token_hashen(token: str) -> str:
    """SHA-256 eines Sitzungstokens (hex).

    Sitzungstokens sind bereits Zufall aus `secrets`, brauchen also kein
    langsames Verfahren — nur einen Einwegschritt, damit ein Blick in die
    Datenbank keine gültigen Tokens hergibt.
    """
    return hashlib.sha256(token.encode("ascii")).hexdigest()
