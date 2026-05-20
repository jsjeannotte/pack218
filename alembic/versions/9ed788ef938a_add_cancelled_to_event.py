"""add cancelled to event

Revision ID: 9ed788ef938a
Revises: 34b4263e0ba3
Create Date: 2026-05-19 22:09:35.460319

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
# https://arunanshub.hashnode.dev/using-sqlmodel-with-alembic
import sqlmodel.sql.sqltypes


# revision identifiers, used by Alembic.
revision: str = '9ed788ef938a'
down_revision: Union[str, None] = '34b4263e0ba3'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add ``cancelled`` as NOT NULL with a server-side default of false so that
    # existing rows get a deterministic value at column-create time. Without a
    # server_default, the ALTER would fail on a table with existing rows.
    with op.batch_alter_table('event', schema=None) as batch_op:
        batch_op.add_column(
            sa.Column('cancelled', sa.Boolean(), nullable=False, server_default=sa.false())
        )


def downgrade() -> None:
    with op.batch_alter_table('event', schema=None) as batch_op:
        batch_op.drop_column('cancelled')
