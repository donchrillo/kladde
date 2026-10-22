"""
Konfiguration des Backends.

Liest Einstellungen aus der `.env` im Repo-Root. Ohne `.env` greifen sinnvolle
Defaults (lokale SQLite-Datei), sodass das Backend out-of-the-box startet.
"""

from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

# backend/src/config.py -> Repo-Root liegt zwei Ebenen höher.
REPO_ROOT = Path(__file__).resolve().parents[2]

# Default-DB: absolute SQLite-Datei unter backend/ (cwd-unabhängig).
DEFAULT_DATABASE_URL = f"sqlite:///{(REPO_ROOT / 'backend' / 'app.db').as_posix()}"

# Ablage der Anhänge. Absolut, damit sie nicht vom Arbeitsverzeichnis abhängt.
DEFAULT_ATTACHMENT_DIR = (REPO_ROOT / "backend" / "attachments").as_posix()


class Settings(BaseSettings):
    """Aus `.env` geladene Laufzeit-Konfiguration."""

    model_config = SettingsConfigDict(
        env_file=REPO_ROOT / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
        populate_by_name=True,
    )

    database_url: str = Field(default=DEFAULT_DATABASE_URL, validation_alias="DATABASE_URL")
    frontend_url: str = Field(default="http://localhost:5173", validation_alias="FRONTEND_URL")

    # Anmeldung. `False` heißt nicht "gesperrt", sondern "jeder ist
    # Administrator" — das Wiki arbeitet dann offen im LAN (siehe src/auth.py).
    # Deshalb ist der Default `True`: geht die `.env` bei einem Deploy verloren
    # oder startet der Dienst im falschen Verzeichnis, ist das Wiki zu und
    # nicht offen. Den offenen Betrieb muss man ausdrücklich einschalten.
    auth_enabled: bool = Field(default=True, validation_alias="AUTH_ENABLED")

    # Gültigkeit einer Sitzung in Tagen, rollierend: jede Anfrage verlängert.
    session_days: int = Field(default=30, validation_alias="SESSION_DAYS")
    # Cookie nur über HTTPS senden. In Produktion hinter Caddy true; im Dev über
    # http://localhost muss es false sein, sonst schickt der Browser es nie mit.
    cookie_secure: bool = Field(default=True, validation_alias="COOKIE_SECURE")

    attachment_dir: str = Field(default=DEFAULT_ATTACHMENT_DIR, validation_alias="ATTACHMENT_DIR")
    # Obergrenze je Datei in Megabyte.
    max_upload_mb: int = Field(default=25, validation_alias="MAX_UPLOAD_MB")


@lru_cache
def get_settings() -> Settings:
    """Gecachte Settings-Instanz (einmal pro Prozess)."""
    return Settings()
