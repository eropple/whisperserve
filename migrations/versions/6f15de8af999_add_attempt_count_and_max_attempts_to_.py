"""Add attempt_count and max_attempts to jobs table

Revision ID: 6f15de8af999
Revises: 0ff973566f8a
Create Date: 2025-03-13 12:41:30.962203

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '6f15de8af999'
down_revision: Union[str, None] = '0ff973566f8a'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # ### commands auto generated by Alembic - please adjust! ###
    op.add_column('jobs', sa.Column('attempt_count', sa.Integer(), nullable=False))
    op.add_column('jobs', sa.Column('max_attempts', sa.Integer(), nullable=False))
    # ### end Alembic commands ###


def downgrade() -> None:
    """Downgrade schema."""
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_column('jobs', 'max_attempts')
    op.drop_column('jobs', 'attempt_count')
    # ### end Alembic commands ###
