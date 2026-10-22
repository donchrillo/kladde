"""Alembic-Umgebung.

Liest die DB-URL aus den App-Settings (`DATABASE_URL`) und nutzt die ORM-Metadaten
aus `src.database.Base`, damit `--autogenerate` Modelländerungen erkennt.
"""

from logging.config import fileConfig

from alembic import context
from sqlalchemy import engine_from_config, pool
from src import models  # noqa: F401  -- registriert die Modelle bei Base.metadata
from src.config import get_settings
from src.database import Base

config = context.config
config.set_main_option("sqlalchemy.url", get_settings().database_url)

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def include_object(objekt, name, typ, reflected, vergleich):  # type: ignore[no-untyped-def]
    """Filtert die FTS5-Tabellen aus dem Autogenerate.

    `page_fts` und ihre Schattentabellen (`page_fts_data`, `page_fts_idx`, …)
    werden per DDL angelegt (siehe src/search.py) und stehen deshalb nicht in
    `Base.metadata`. Ohne diesen Filter hielte Alembic sie für verwaiste
    Tabellen und schriebe in jede neue Migration ein `drop_table` — was den
    Suchindex bei der nächsten Migration stillschweigend vernichten würde.
    """
    return not (typ == "table" and name is not None and name.startswith("page_fts"))


def run_migrations_offline() -> None:
    """Migrationen ohne aktive DB-Verbindung (SQL-Skript-Ausgabe)."""
    context.configure(
        url=config.get_main_option("sqlalchemy.url"),
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        render_as_batch=True,
        include_object=include_object,
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Migrationen gegen eine aktive DB-Verbindung."""
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    with connectable.connect() as connection:
        # render_as_batch: nötig für ALTER TABLE unter SQLite.
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            render_as_batch=True,
            include_object=include_object,
        )
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
