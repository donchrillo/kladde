"""Slug-Erzeugung für Seiten- und Bereichs-URLs."""

import re
import unicodedata

# Deutsche Sonderzeichen zuerst ersetzen, sonst fallen die Umlaute bei der
# Unicode-Normalisierung auf den nackten Vokal zurück ("Bücher" -> "bcher").
_UMLAUTE = {
    "ä": "ae",
    "ö": "oe",
    "ü": "ue",
    "ß": "ss",
}


def slugify(text: str) -> str:
    """Wandelt einen Titel in einen URL-tauglichen Slug.

    Leerer oder rein symbolischer Text ergibt ``"seite"``, damit nie ein leerer
    Slug in der Datenbank landet.
    """
    text = text.lower()
    for zeichen, ersatz in _UMLAUTE.items():
        text = text.replace(zeichen, ersatz)
    # Restliche Akzente entfernen (é -> e).
    text = unicodedata.normalize("NFKD", text)
    text = "".join(z for z in text if not unicodedata.combining(z))
    text = re.sub(r"[^a-z0-9]+", "-", text).strip("-")
    return text or "seite"
