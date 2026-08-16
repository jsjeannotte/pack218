"""add family event payments

Revision ID: d7f2b91c6a40
Revises: 9ed788ef938a
Create Date: 2026-08-15 00:00:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "d7f2b91c6a40"
down_revision: Union[str, None] = "9ed788ef938a"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "family_event_payment",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("event_id", sa.Integer(), nullable=False),
        sa.Column("family_id", sa.Integer(), nullable=False),
        sa.Column("is_paid", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.ForeignKeyConstraint(["event_id"], ["event.id"], name=op.f("fk_family_event_payment_event_id_event")),
        sa.ForeignKeyConstraint(["family_id"], ["family.id"], name=op.f("fk_family_event_payment_family_id_family")),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_family_event_payment")),
        sa.UniqueConstraint("event_id", "family_id", name="uq_family_event_payment"),
    )
    with op.batch_alter_table("family_event_payment", schema=None) as batch_op:
        batch_op.create_index("ix_family_event_payment_event_id", ["event_id"], unique=False)

    # Preserve the meaning of the legacy per-person flag where it was
    # unambiguous: a family/event is complete only when every registration
    # had been marked paid. Partial legacy flags remain unpaid for review.
    op.execute(sa.text("""
        INSERT INTO family_event_payment (event_id, family_id, is_paid)
        SELECT er.event_id, u.family_id, true
        FROM eventregistration AS er
        JOIN user AS u ON u.id = er.user_id
        WHERE u.family_id IS NOT NULL
        GROUP BY er.event_id, u.family_id
        HAVING MIN(CASE WHEN er.has_paid THEN 1 ELSE 0 END) = 1
    """))


def downgrade() -> None:
    with op.batch_alter_table("family_event_payment", schema=None) as batch_op:
        batch_op.drop_index("ix_family_event_payment_event_id")
    op.drop_table("family_event_payment")
