"""Ensure primary key and unique constraint on holidays table

Revision ID: b5495c32909e
Revises: 6f38efed51af
Create Date: 2025-05-05 17:11:46.590209

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "b5495c32909e"
down_revision: Union[str, None] = "6f38efed51af"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

uq_name = "uq_holidays_date"


def upgrade() -> None:
    print(f"Attempting to ensure unique constraint for 'holidays.date'...")

    try:

        op.create_unique_constraint(uq_name, "holidays", ["date"])
        print(f"Created unique constraint: {uq_name} on holidays(date)")
    except Exception as e:

        print(
            f"Could not create unique constraint {uq_name} (maybe it already exists?): {e}"
        )


def downgrade() -> None:
    print(f"Attempting to drop unique constraint for 'holidays.date'...")
    try:
        op.drop_constraint(uq_name, "holidays", type_="unique")
        print(f"Dropped unique constraint: {uq_name}")
    except Exception as e:
        print(
            f"Could not drop unique constraint {uq_name} (maybe it doesn't exist?): {e}"
        )
