"""cross_tenant_batch_alerts

Revision ID: 0022
Revises: 0021
Create Date: 2026-09-06

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '0022'
down_revision: Union[str, None] = '0021'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table('cross_tenant_batch_alerts',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('medicine_name', sa.String(length=255), nullable=False),
        sa.Column('normalized_batch_no', sa.String(length=100), nullable=False),
        sa.Column('tenant_ids', sa.Text(), nullable=False),
        sa.Column('distributor_names', sa.Text(), nullable=False),
        sa.Column('occurrence_count', sa.Integer(), nullable=False),
        sa.Column('first_seen', sa.DateTime(), nullable=True),
        sa.Column('last_seen', sa.DateTime(), nullable=True),
        sa.Column('status', sa.Enum('open', 'reviewed', 'dismissed', name='cross_tenant_alert_status'), server_default='open', nullable=False),
        sa.Column('severity', sa.Enum('medium', 'high', name='cross_tenant_alert_severity'), server_default='high', nullable=False),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('now()'), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('normalized_batch_no', 'medicine_name', name='uix_batch_medicine')
    )
    op.create_index(op.f('ix_cross_tenant_batch_alerts_id'), 'cross_tenant_batch_alerts', ['id'], unique=False)
    op.create_index(op.f('ix_cross_tenant_batch_alerts_normalized_batch_no'), 'cross_tenant_batch_alerts', ['normalized_batch_no'], unique=False)
    
    op.execute("ALTER TABLE notifications MODIFY COLUMN notification_type ENUM('adherence_overdue', 'anomaly_flagged', 'low_stock_crossed', 'credit_overdue', 'trust_chain_tamper', 'near_expiry', 'daily_digest', 'system', 'cross_tenant_alert') NOT NULL")


def downgrade() -> None:
    op.execute("ALTER TABLE notifications MODIFY COLUMN notification_type ENUM('adherence_overdue', 'anomaly_flagged', 'low_stock_crossed', 'credit_overdue', 'trust_chain_tamper', 'near_expiry', 'daily_digest', 'system') NOT NULL")
    op.drop_index(op.f('ix_cross_tenant_batch_alerts_normalized_batch_no'), table_name='cross_tenant_batch_alerts')
    op.drop_index(op.f('ix_cross_tenant_batch_alerts_id'), table_name='cross_tenant_batch_alerts')
    op.drop_table('cross_tenant_batch_alerts')
