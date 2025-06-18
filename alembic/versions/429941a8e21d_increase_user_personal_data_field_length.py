"""increase_user_personal_data_field_length

Revision ID: 429941a8e21d
Revises: 7990c409f90a
Create Date: 2025-05-30 18:01:06.124786

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "429941a8e21d"
down_revision: Union[str, None] = "7990c409f90a"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.alter_column(
        "users",
        "email",
        existing_type=sa.VARCHAR(length=100),
        type_=sa.String(length=255),
        existing_nullable=False,
    )
    op.alter_column(
        "users",
        "full_name",
        existing_type=sa.VARCHAR(length=100),
        type_=sa.String(length=255),
        existing_nullable=False,
    )
    op.alter_column(
        "users",
        "phone",
        existing_type=sa.VARCHAR(length=20),
        type_=sa.String(length=255),
        existing_nullable=True,
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.alter_column(
        "users",
        "phone",
        existing_type=sa.String(length=255),
        type_=sa.VARCHAR(length=20),  # Возвращаем к String(20)
        existing_nullable=True,
    )
    op.alter_column(
        "users",
        "full_name",
        existing_type=sa.String(length=255),
        type_=sa.VARCHAR(length=100),  # Возвращаем к String(100)
        existing_nullable=False,
    )
    op.alter_column(
        "users",
        "email",
        existing_type=sa.String(length=255),
        type_=sa.VARCHAR(length=100),  # Возвращаем к String(100)
        existing_nullable=False,
    )
