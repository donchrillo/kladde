"""initial: Wiki-Schema (space, page, page_version)

Revision ID: 0001
Revises:
Create Date: Phase 1 (Wiki-Datenmodell)
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "space",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("key", sa.String(), nullable=False),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("description", sa.String(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(),
            server_default=sa.text("(CURRENT_TIMESTAMP)"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    with op.batch_alter_table("space", schema=None) as batch_op:
        batch_op.create_index(batch_op.f("ix_space_key"), ["key"], unique=True)

    op.create_table(
        "page",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("space_id", sa.Integer(), nullable=False),
        sa.Column("parent_id", sa.Integer(), nullable=True),
        sa.Column("title", sa.String(), nullable=False),
        sa.Column("slug", sa.String(), nullable=False),
        sa.Column("body", sa.String(), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(),
            server_default=sa.text("(CURRENT_TIMESTAMP)"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(),
            server_default=sa.text("(CURRENT_TIMESTAMP)"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["parent_id"],
            ["page.id"],
        ),
        sa.ForeignKeyConstraint(
            ["space_id"],
            ["space.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("space_id", "slug", name="uq_page_space_slug"),
    )
    with op.batch_alter_table("page", schema=None) as batch_op:
        batch_op.create_index(batch_op.f("ix_page_parent_id"), ["parent_id"], unique=False)
        batch_op.create_index(batch_op.f("ix_page_slug"), ["slug"], unique=False)
        batch_op.create_index(batch_op.f("ix_page_space_id"), ["space_id"], unique=False)

    op.create_table(
        "page_version",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("page_id", sa.Integer(), nullable=False),
        sa.Column("revision", sa.Integer(), nullable=False),
        sa.Column("title", sa.String(), nullable=False),
        sa.Column("body", sa.String(), nullable=False),
        sa.Column("author", sa.String(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(),
            server_default=sa.text("(CURRENT_TIMESTAMP)"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["page_id"],
            ["page.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("page_id", "revision", name="uq_page_version_revision"),
    )
    with op.batch_alter_table("page_version", schema=None) as batch_op:
        batch_op.create_index(batch_op.f("ix_page_version_page_id"), ["page_id"], unique=False)


def downgrade() -> None:
    with op.batch_alter_table("page_version", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_page_version_page_id"))

    op.drop_table("page_version")
    with op.batch_alter_table("page", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_page_space_id"))
        batch_op.drop_index(batch_op.f("ix_page_slug"))
        batch_op.drop_index(batch_op.f("ix_page_parent_id"))

    op.drop_table("page")
    with op.batch_alter_table("space", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_space_key"))

    op.drop_table("space")
