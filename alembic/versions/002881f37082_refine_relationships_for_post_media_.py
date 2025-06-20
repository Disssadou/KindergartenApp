"""refine_relationships_for_post_media_group

Revision ID: 002881f37082
Revises: b9e45417be44
Create Date: 2025-05-12 13:45:55.275044

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '002881f37082'
down_revision: Union[str, None] = 'b9e45417be44'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # ### commands auto generated by Alembic - please adjust! ###
    op.alter_column('attendances', 'absence_type',
               existing_type=sa.VARCHAR(length=20),
               comment='sick_leave, vacation, other',
               existing_comment='Тип отсутствия (sick_leave, vacation, other)',
               existing_nullable=True)
    op.create_unique_constraint(None, 'groups', ['name'])
    op.add_column('media', sa.Column('group_id', sa.Integer(), nullable=True))
    op.create_index(op.f('ix_media_group_id'), 'media', ['group_id'], unique=False)
    op.create_foreign_key(None, 'media', 'groups', ['group_id'], ['id'], ondelete='SET NULL')
    op.add_column('notifications', sa.Column('is_event', sa.Boolean(), nullable=False))
    op.add_column('notifications', sa.Column('event_date', sa.DateTime(timezone=True), nullable=True))
    op.alter_column('notifications', 'title',
               existing_type=sa.VARCHAR(length=200),
               type_=sa.String(length=255),
               existing_nullable=False)
    op.drop_index('ix_notification_recipient_read_created', table_name='notifications')
    op.drop_index('ix_notifications_created_at', table_name='notifications')
    op.drop_index('ix_notifications_is_read', table_name='notifications')
    op.drop_index('ix_notifications_recipient_id', table_name='notifications')
    op.drop_index('ix_notifications_type', table_name='notifications')
    op.create_index(op.f('ix_notifications_id'), 'notifications', ['id'], unique=False)
    op.drop_constraint('notifications_recipient_id_fkey', 'notifications', type_='foreignkey')
    op.drop_column('notifications', 'is_read')
    op.drop_column('notifications', 'related_entity_type')
    op.drop_column('notifications', 'related_entity_id')
    op.drop_column('notifications', 'recipient_id')
    op.drop_column('notifications', 'type')
    op.drop_column('notifications', 'read_at')
    op.create_index(op.f('ix_posts_author_id'), 'posts', ['author_id'], unique=False)
    # ### end Alembic commands ###


def downgrade() -> None:
    """Downgrade schema."""
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_index(op.f('ix_posts_author_id'), table_name='posts')
    op.add_column('notifications', sa.Column('read_at', postgresql.TIMESTAMP(timezone=True), autoincrement=False, nullable=True))
    op.add_column('notifications', sa.Column('type', sa.VARCHAR(length=50), autoincrement=False, nullable=False))
    op.add_column('notifications', sa.Column('recipient_id', sa.BIGINT(), autoincrement=False, nullable=False))
    op.add_column('notifications', sa.Column('related_entity_id', sa.BIGINT(), autoincrement=False, nullable=True))
    op.add_column('notifications', sa.Column('related_entity_type', sa.VARCHAR(length=50), autoincrement=False, nullable=True))
    op.add_column('notifications', sa.Column('is_read', sa.BOOLEAN(), autoincrement=False, nullable=False))
    op.create_foreign_key('notifications_recipient_id_fkey', 'notifications', 'users', ['recipient_id'], ['id'], ondelete='CASCADE')
    op.drop_index(op.f('ix_notifications_id'), table_name='notifications')
    op.create_index('ix_notifications_type', 'notifications', ['type'], unique=False)
    op.create_index('ix_notifications_recipient_id', 'notifications', ['recipient_id'], unique=False)
    op.create_index('ix_notifications_is_read', 'notifications', ['is_read'], unique=False)
    op.create_index('ix_notifications_created_at', 'notifications', ['created_at'], unique=False)
    op.create_index('ix_notification_recipient_read_created', 'notifications', ['recipient_id', 'is_read', 'created_at'], unique=False)
    op.alter_column('notifications', 'title',
               existing_type=sa.String(length=255),
               type_=sa.VARCHAR(length=200),
               existing_nullable=False)
    op.drop_column('notifications', 'event_date')
    op.drop_column('notifications', 'is_event')
    op.drop_constraint(None, 'media', type_='foreignkey')
    op.drop_index(op.f('ix_media_group_id'), table_name='media')
    op.drop_column('media', 'group_id')
    op.drop_constraint(None, 'groups', type_='unique')
    op.alter_column('attendances', 'absence_type',
               existing_type=sa.VARCHAR(length=20),
               comment='Тип отсутствия (sick_leave, vacation, other)',
               existing_comment='sick_leave, vacation, other',
               existing_nullable=True)
    # ### end Alembic commands ###
