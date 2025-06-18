"""remove_selected_created_updated_at_fields

Revision ID: 50a155c3777d
Revises: ad01ef180521
Create Date: 2025-06-01 16:48:35.423983

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.sql import func

# revision identifiers, used by Alembic.
revision: str = "50a155c3777d"
down_revision: Union[str, None] = "ad01ef180521"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    print("Dropping selected created_at/updated_at columns...")
    # child_parents
    op.drop_column("child_parents", "created_at")
    op.drop_column("child_parents", "updated_at")
    print("- child_parents: dropped created_at, updated_at")

    # meal_menus
    op.drop_column("meal_menus", "created_at")
    op.drop_column("meal_menus", "updated_at")
    print("- meal_menus: dropped created_at, updated_at")

    # posts
    op.drop_column("posts", "updated_at")
    print("- posts: dropped updated_at")

    # notifications
    op.drop_column("notifications", "updated_at")
    print("- notifications: dropped updated_at")

    # events
    op.drop_column("events", "updated_at")
    print("- events: dropped updated_at")

    # users
    op.drop_column("users", "updated_at")
    print("- users: dropped updated_at")

    # children
    op.drop_column("children", "updated_at")
    print("- children: dropped updated_at")

    # groups
    op.drop_column("groups", "created_at")
    op.drop_column("groups", "updated_at")
    print("- groups: dropped created_at, updated_at")

    # attendances
    op.drop_column("attendances", "updated_at")
    print("- attendances: dropped updated_at")
    print("Finished dropping columns.")


def downgrade() -> None:
    print("Adding back selected created_at/updated_at columns...")
    # attendances
    op.add_column(
        "attendances",
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=func.now(),
            onupdate=func.now(),
            nullable=False,
        ),
    )
    print("+ attendances: added updated_at")

    # groups
    op.add_column(
        "groups",
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=func.now(),
            onupdate=func.now(),
            nullable=False,
        ),
    )
    op.add_column(
        "groups",
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=func.now(),
            nullable=False,
        ),
    )
    print("+ groups: added created_at, updated_at")

    # children
    op.add_column(
        "children",
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=func.now(),
            onupdate=func.now(),
            nullable=False,
        ),
    )
    print("+ children: added updated_at")

    # users
    op.add_column(
        "users",
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=func.now(),
            onupdate=func.now(),
            nullable=False,
        ),
    )
    print("+ users: added updated_at")

    # events
    op.add_column(
        "events",
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=func.now(),
            onupdate=func.now(),
            nullable=False,
        ),
    )
    print("+ events: added updated_at")

    # notifications
    op.add_column(
        "notifications",
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=func.now(),
            onupdate=func.now(),
            nullable=False,
        ),
    )
    print("+ notifications: added updated_at")

    # posts
    op.add_column(
        "posts",
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=func.now(),
            onupdate=func.now(),
            nullable=False,
        ),
    )
    print("+ posts: added updated_at")

    # meal_menus
    op.add_column(
        "meal_menus",
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=func.now(),
            onupdate=func.now(),
            nullable=False,
        ),
    )
    op.add_column(
        "meal_menus",
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=func.now(),
            nullable=False,
        ),
    )
    print("+ meal_menus: added created_at, updated_at")

    # child_parents
    op.add_column(
        "child_parents",
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=func.now(),
            onupdate=func.now(),
            nullable=False,
        ),
    )
    op.add_column(
        "child_parents",
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=func.now(),
            nullable=False,
        ),
    )
    print("+ child_parents: added created_at, updated_at")
    print("Finished adding back columns.")
