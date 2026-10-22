"""privatbereiche und rechtestufen

Zieht drei Spalten ein: `space.owner_id` und `space.is_private` fuer private
Bereiche, `user.darf_bereiche_anlegen` fuer das Anlegen von Bereichen ohne
Administratorrecht.

Die vierte Rechtestufe `LOESCHEN` braucht kein DDL: `space_permission.level`
ist ein `Enum(native_enum=False)`, also VARCHAR ohne CHECK, und "LOESCHEN" ist
kuerzer als das bisher laengste "VERWALTEN".

Revision ID: 7c3a1b9de204
Revises: 46f1f05fee9f
Create Date: 2026-09-05
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "7c3a1b9de204"
down_revision: str | None = "46f1f05fee9f"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("space", schema=None) as batch_op:
        batch_op.add_column(sa.Column("owner_id", sa.Integer(), nullable=True))
        batch_op.add_column(
            sa.Column("is_private", sa.Boolean(), nullable=False, server_default=sa.false())
        )
        batch_op.create_index(batch_op.f("ix_space_owner_id"), ["owner_id"], unique=False)
        batch_op.create_foreign_key("fk_space_owner_id_user", "user", ["owner_id"], ["id"])

    with op.batch_alter_table("user", schema=None) as batch_op:
        batch_op.add_column(
            sa.Column(
                "darf_bereiche_anlegen", sa.Boolean(), nullable=False, server_default=sa.false()
            )
        )

    # Bestand: Bereiche, die exakt so heissen wie der Anzeigename eines Kontos,
    # werden zum Privatbereich dieses Kontos. Bewusst ueber diese Regel statt
    # ueber einen hartkodierten Namen — sie beschreibt genau die Konvention,
    # nach der der Bereich "Anna Beispiel" bisher angelegt wurde. Trifft die
    # Regel auf nichts zu, passiert schlicht nichts.
    op.execute(sa.text("""
            UPDATE space
               SET owner_id = (SELECT u.id FROM user u WHERE u.display_name = space.name),
                   is_private = 1
             WHERE EXISTS (SELECT 1 FROM user u WHERE u.display_name = space.name)
            """))

    # Die server_defaults haben nur den Bestand gefuellt; kuenftige Zeilen
    # bringen ihren Wert aus dem Modell mit.
    with op.batch_alter_table("space", schema=None) as batch_op:
        batch_op.alter_column("is_private", server_default=None)
    with op.batch_alter_table("user", schema=None) as batch_op:
        batch_op.alter_column("darf_bereiche_anlegen", server_default=None)


def downgrade() -> None:
    with op.batch_alter_table("user", schema=None) as batch_op:
        batch_op.drop_column("darf_bereiche_anlegen")

    with op.batch_alter_table("space", schema=None) as batch_op:
        batch_op.drop_constraint("fk_space_owner_id_user", type_="foreignkey")
        batch_op.drop_index(batch_op.f("ix_space_owner_id"))
        batch_op.drop_column("is_private")
        batch_op.drop_column("owner_id")
