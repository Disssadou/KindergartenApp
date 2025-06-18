"""increase_user_personal_data_field_length

Revision ID: e0a37fcd0409
Revises: f9da1f247cd1
Create Date: 2025-05-30 17:51:34.289826

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'e0a37fcd0409'
down_revision: Union[str, None] = 'f9da1f247cd1'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
