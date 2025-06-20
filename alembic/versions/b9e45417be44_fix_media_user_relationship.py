"""fix_media_user_relationship

Revision ID: b9e45417be44
Revises: c5b752cd10f3
Create Date: 2025-05-12 13:32:52.481335

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'b9e45417be44'
down_revision: Union[str, None] = 'c5b752cd10f3'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # ### commands auto generated by Alembic - please adjust! ###
    op.create_index(op.f('ix_media_uploaded_by_id'), 'media', ['uploaded_by_id'], unique=False)
    # ### end Alembic commands ###


def downgrade() -> None:
    """Downgrade schema."""
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_index(op.f('ix_media_uploaded_by_id'), table_name='media')
    # ### end Alembic commands ###
