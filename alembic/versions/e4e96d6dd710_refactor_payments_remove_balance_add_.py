"""refactor_payments_remove_balance_add_monthly_charge

Revision ID: e4e96d6dd710
Revises: aa1bac681b31
Create Date: 2025-05-30 20:24:23.814051

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "e4e96d6dd710"
down_revision: Union[str, None] = "aa1bac681b31"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    if "balance_transactions" in inspector.get_table_names():
        op.drop_table("balance_transactions")
        print("Dropped table balance_transactions.")
    else:
        print("Table balance_transactions does not exist, skipping drop.")

    try:
        op.drop_column("children", "balance")
        print("Dropped column balance from children.")
    except Exception as e:
        print(
            f"Could not drop column balance from children (maybe it doesn't exist?): {e}"
        )

    op.alter_column(
        "children",
        "birth_date",
        existing_type=sa.DATE(),
        type_=sa.String(length=255),
        existing_nullable=False,
    )
    print("Altered column birth_date in children to String(255).")

    op.create_table(
        "monthly_charges",
        sa.Column("id", sa.BigInteger(), nullable=False),
        sa.Column("child_id", sa.BigInteger(), nullable=False),
        sa.Column("year", sa.Integer(), nullable=False),
        sa.Column("month", sa.Integer(), nullable=False),
        sa.Column("amount_due", sa.Numeric(precision=10, scale=2), nullable=False),
        sa.Column("calculation_details", sa.Text(), nullable=True),
        sa.Column(
            "calculated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["child_id"], ["children.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "child_id", "year", "month", name="uq_child_monthly_charge"
        ),
        sa.CheckConstraint(
            "month >= 1 AND month <= 12", name="check_charge_month_range"
        ),
    )
    op.create_index(
        op.f("ix_monthly_charges_child_id"),
        "monthly_charges",
        ["child_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_monthly_charges_year"), "monthly_charges", ["year"], unique=False
    )
    op.create_index(
        op.f("ix_monthly_charges_month"), "monthly_charges", ["month"], unique=False
    )
    op.create_index(
        "ix_monthly_charges_child_year_month",
        "monthly_charges",
        ["child_id", "year", "month"],
        unique=False,
    )  # Добавил этот индекс, как в модели
    print("Created table monthly_charges with indexes and constraints.")


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(
        "ix_monthly_charges_child_year_month", table_name="monthly_charges"
    )  # Сначала удаляем индексы
    op.drop_index(op.f("ix_monthly_charges_month"), table_name="monthly_charges")
    op.drop_index(op.f("ix_monthly_charges_year"), table_name="monthly_charges")
    op.drop_index(op.f("ix_monthly_charges_child_id"), table_name="monthly_charges")
    op.drop_table("monthly_charges")
    print("Dropped table monthly_charges.")

    op.alter_column(
        "children",
        "birth_date",
        existing_type=sa.String(length=255),
        type_=sa.DATE(),
        existing_nullable=False,
    )
    print("Altered column birth_date in children back to DATE.")

    op.add_column(
        "children",
        sa.Column(
            "balance",
            sa.Numeric(precision=10, scale=2),
            server_default=sa.text("'0.00'"),
            nullable=False,
        ),
    )
    print("Added column balance back to children.")
