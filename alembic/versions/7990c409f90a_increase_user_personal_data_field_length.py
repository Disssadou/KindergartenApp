"""increase_user_personal_data_field_length

Revision ID: 7990c409f90a
Revises: e0a37fcd0409
Create Date: 2025-05-30 17:53:29.730510

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '7990c409f90a'
down_revision: Union[str, None] = 'e0a37fcd0409'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
