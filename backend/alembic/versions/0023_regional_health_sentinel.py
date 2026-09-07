"""regional_health_sentinel

Revision ID: 0023
Revises: 0022
Create Date: 2026-09-07

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '0023'
down_revision: Union[str, None] = '0022'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # -----------------------------------------------------------------------
    # 1. Add region_code and surveillance_opt_in to tenants table.
    # -----------------------------------------------------------------------
    op.add_column('tenants', sa.Column('region_code', sa.String(length=50), nullable=True))
    op.add_column('tenants', sa.Column('surveillance_opt_in', sa.Boolean(), nullable=False, server_default='0'))

    # -----------------------------------------------------------------------
    # 2. Create regional_health_alerts table.
    # -----------------------------------------------------------------------
    op.create_table(
        'regional_health_alerts',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('region_code', sa.String(length=50), nullable=False),
        sa.Column('condition_name', sa.String(length=150), nullable=False),
        sa.Column('alert_date', sa.Date(), nullable=False),
        sa.Column('contributing_tenant_count', sa.Integer(), nullable=False),
        sa.Column('total_regional_units', sa.Integer(), nullable=False),
        sa.Column('regional_avg_units', sa.Numeric(10, 2), nullable=False),
        sa.Column('z_score', sa.Numeric(6, 3), nullable=False),
        sa.Column(
            'severity',
            sa.Enum('watch', 'elevated', 'critical', name='regional_alert_severity'),
            nullable=False,
            server_default='watch',
        ),
        sa.Column(
            'status',
            sa.Enum('open', 'acknowledged', 'dismissed', name='regional_alert_status'),
            nullable=False,
            server_default='open',
        ),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('now()'), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('region_code', 'condition_name', 'alert_date', name='uix_regional_alert_region_cond_date'),
    )
    op.create_index(op.f('ix_regional_health_alerts_id'), 'regional_health_alerts', ['id'], unique=False)
    op.create_index(op.f('ix_regional_health_alerts_region_code'), 'regional_health_alerts', ['region_code'], unique=False)
    op.create_index('ix_regional_health_alerts_region_date', 'regional_health_alerts', ['region_code', 'alert_date'], unique=False)

    # -----------------------------------------------------------------------
    # 3. Fix the SurveillanceDailyCount unique constraint to include tenant_id.
    #    The original constraint (condition_name, count_date) without tenant_id
    #    prevents multi-tenant per-pharmacy counts.  This change makes the
    #    constraint (tenant_id, condition_name, count_date), which allows each
    #    opted-in pharmacy to maintain its own daily counts — a prerequisite
    #    for the cross-tenant regional aggregation this migration introduces.
    # -----------------------------------------------------------------------
    op.drop_constraint('uq_surveillance_daily_counts_cond_date', 'surveillance_daily_counts', type_='unique')
    op.create_unique_constraint(
        'uq_surveillance_daily_counts_tenant_cond_date',
        'surveillance_daily_counts',
        ['tenant_id', 'condition_name', 'count_date'],
    )

    # -----------------------------------------------------------------------
    # 4. Add 'regional_health_spike' to the notifications enum, following the
    #    exact same ALTER TABLE pattern used in migration 0022 for
    #    'cross_tenant_alert'.
    # -----------------------------------------------------------------------
    op.execute(
        "ALTER TABLE notifications MODIFY COLUMN notification_type "
        "ENUM('adherence_overdue', 'anomaly_flagged', 'low_stock_crossed', "
        "'credit_overdue', 'trust_chain_tamper', 'near_expiry', 'daily_digest', "
        "'system', 'cross_tenant_alert', 'regional_health_spike') NOT NULL"
    )


def downgrade() -> None:
    op.execute(
        "ALTER TABLE notifications MODIFY COLUMN notification_type "
        "ENUM('adherence_overdue', 'anomaly_flagged', 'low_stock_crossed', "
        "'credit_overdue', 'trust_chain_tamper', 'near_expiry', 'daily_digest', "
        "'system', 'cross_tenant_alert') NOT NULL"
    )

    op.drop_constraint('uq_surveillance_daily_counts_tenant_cond_date', 'surveillance_daily_counts', type_='unique')
    op.create_unique_constraint(
        'uq_surveillance_daily_counts_cond_date',
        'surveillance_daily_counts',
        ['condition_name', 'count_date'],
    )

    op.drop_index('ix_regional_health_alerts_region_date', table_name='regional_health_alerts')
    op.drop_index(op.f('ix_regional_health_alerts_region_code'), table_name='regional_health_alerts')
    op.drop_index(op.f('ix_regional_health_alerts_id'), table_name='regional_health_alerts')
    op.drop_table('regional_health_alerts')

    op.drop_column('tenants', 'surveillance_opt_in')
    op.drop_column('tenants', 'region_code')
