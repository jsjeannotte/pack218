"""add action log

Revision ID: 34b4263e0ba3
Revises: efdb27d61ada
Create Date: 2026-05-11 12:38:28.000026

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
# https://arunanshub.hashnode.dev/using-sqlmodel-with-alembic
import sqlmodel.sql.sqltypes


# revision identifiers, used by Alembic.
revision: str = '34b4263e0ba3'
down_revision: Union[str, None] = 'efdb27d61ada'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'action_log',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('actor_user_id', sa.Integer(), nullable=True),
        sa.Column('subject_user_id', sa.Integer(), nullable=True),
        sa.Column('entity_name', sa.String(), nullable=False),
        sa.Column('entity_id', sa.Integer(), nullable=False),
        sa.Column('action', sa.String(), nullable=False),
        sa.Column('field_changes', sa.JSON(), nullable=False),
        sa.Column('reason', sqlmodel.sql.sqltypes.AutoString(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['actor_user_id'], ['user.id'], name=op.f('fk_action_log_actor_user_id_user')),
        sa.ForeignKeyConstraint(['subject_user_id'], ['user.id'], name=op.f('fk_action_log_subject_user_id_user')),
        sa.PrimaryKeyConstraint('id', name=op.f('pk_action_log')),
    )
    with op.batch_alter_table('action_log', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_action_log_actor_user_id'), ['actor_user_id'], unique=False)
        batch_op.create_index('ix_action_log_entity', ['entity_name', 'entity_id'], unique=False)
        batch_op.create_index('ix_action_log_subject_created', ['subject_user_id', 'created_at'], unique=False)


def downgrade() -> None:
    with op.batch_alter_table('action_log', schema=None) as batch_op:
        batch_op.drop_index('ix_action_log_subject_created')
        batch_op.drop_index('ix_action_log_entity')
        batch_op.drop_index(batch_op.f('ix_action_log_actor_user_id'))

    op.drop_table('action_log')
