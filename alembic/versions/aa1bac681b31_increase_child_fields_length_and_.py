"""increase_child_fields_length_and_prepare_for_encryption

Revision ID: aa1bac681b31
Revises: 429941a8e21d
Create Date: 2025-05-30 18:32:57.860981

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "aa1bac681b31"
down_revision: Union[str, None] = "429941a8e21d"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.alter_column(
        "children",
        "full_name",
        existing_type=sa.VARCHAR(length=100),
        type_=sa.String(length=255),
        existing_nullable=False,
    )
    op.alter_column(
        "children",
        "address",
        existing_type=sa.VARCHAR(length=200),
        type_=sa.String(length=512),
        existing_nullable=True,
    )

    op.alter_column(
        "children",
        "birth_date",
        existing_type=sa.DATE(),
        type_=sa.String(length=255),
        existing_nullable=False,
    )


def downgrade() -> None:
    op.alter_column(
        "children",
        "birth_date",
        existing_type=sa.String(length=255),
        type_=sa.DATE(),
        existing_nullable=False,
    )
    op.alter_column(
        "children",
        "address",
        existing_type=sa.String(length=512),
        type_=sa.VARCHAR(length=200),
        existing_nullable=True,
    )
    op.alter_column(
        "children",
        "full_name",
        existing_type=sa.String(length=255),
        type_=sa.VARCHAR(length=100),
        existing_nullable=False,
    )
