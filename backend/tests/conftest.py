"""Test-Fixtures: jede Testfunktion bekommt eine frische In-Memory-SQLite.

Die echte Datei-DB wird nie berührt — `get_db` wird per Dependency-Override auf
eine isolierte In-Memory-Engine umgebogen.
"""

from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool
from src.anmeldeschutz import zuruecksetzen
from src.config import get_settings
from src.database import Base, get_db
from src.main import app


@pytest.fixture(autouse=True)
def anhang_ablage(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[Path]:
    """Kappt die Verbindung zur echten Betriebskonfiguration.

    Zwei Dinge dürfen nicht aus der `.env` des laufenden Systems kommen:

    * **Der Anhang-Ordner** — sonst schrieben Tests nach `backend/attachments`.
    * **`AUTH_ENABLED`** — die Fachtests fahren bewusst im offenen Betrieb. Seit
      die Anmeldung scharf ist, stünde sonst vor jedem Test ein 401. Wer eine
      echte Anmeldung braucht, schaltet sie in seinem Test wieder ein (siehe
      `mit_anmeldung` in `test_auth.py`).
    """
    ordner = tmp_path / "attachments"
    monkeypatch.setenv("ATTACHMENT_DIR", str(ordner))
    monkeypatch.setenv("AUTH_ENABLED", "false")
    get_settings.cache_clear()
    yield ordner
    get_settings.cache_clear()


@pytest.fixture(autouse=True)
def anmeldeschutz_zuruecksetzen() -> Iterator[None]:
    """Fehlversuchszähler zwischen den Tests leeren.

    Die Sperre gegen Passwort-Raten lebt im Prozess. Ohne dieses Zurücksetzen
    schleppte ein Test mit absichtlich falschen Passwörtern seine Sperre in den
    nächsten — die Reihenfolge der Tests entschiede dann über ihr Ergebnis.
    """
    zuruecksetzen()
    yield
    zuruecksetzen()


@pytest.fixture
def mit_anmeldung(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    """Schaltet die Anmeldung für diesen einen Test scharf.

    Liegt hier statt in einer einzelnen Testdatei, weil inzwischen mehrere
    Dateien einen echten Login brauchen — private Bereiche lassen sich im
    offenen Betrieb gar nicht prüfen, dort gibt es keinen Eigentümer.
    """
    monkeypatch.setenv("AUTH_ENABLED", "true")
    # Ohne TLS im Test würde der TestClient das Secure-Cookie nicht mitschicken.
    monkeypatch.setenv("COOKIE_SECURE", "false")
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


@pytest.fixture
def db_session() -> Iterator[Session]:
    # StaticPool + "sqlite://" => eine geteilte In-Memory-DB für diese Verbindung.
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    testing_session = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    session = testing_session()
    try:
        yield session
    finally:
        session.close()
        engine.dispose()


@pytest.fixture
def client(db_session: Session) -> Iterator[TestClient]:
    def override_get_db() -> Iterator[Session]:
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()
