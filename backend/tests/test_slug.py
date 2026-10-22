"""Tests für die Slug-Erzeugung."""

import pytest
from src.slug import slugify


@pytest.mark.parametrize(
    ("text", "erwartet"),
    [
        ("Einstieg", "einstieg"),
        ("IT & Büro", "it-buero"),
        ("Über größere Anlässe", "ueber-groessere-anlaesse"),
        ("Café-Ecke", "cafe-ecke"),
        ("  mehrere   Leerzeichen  ", "mehrere-leerzeichen"),
        ("###", "seite"),
    ],
)
def test_slugify(text: str, erwartet: str) -> None:
    assert slugify(text) == erwartet
