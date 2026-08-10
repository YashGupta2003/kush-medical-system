"""surveillance cold chain

Revision ID: 0014_surveillance_cold_chain
Revises: 0013_notifications_whatsapp
Create Date: 2026-08-10 11:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '0014_surveillance_cold_chain'
down_revision = '0013_notifications_whatsapp'
branch_labels = None
depends_on = None


def upgrade():
    # 1. Add medicine_batches.is_cold_chain
    op.add_column('medicine_batches', sa.Column('is_cold_chain', sa.Boolean(), nullable=True, server_default=sa.text('0')))
    
    # 2. Create cold_chain_units table
    op.create_table('cold_chain_units',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('unit_label', sa.String(length=100), nullable=False),
        sa.Column('location_note', sa.String(length=255), nullable=True),
        sa.Column('min_temp_c', sa.Numeric(precision=5, scale=2), nullable=False, server_default='2.0'),
        sa.Column('max_temp_c', sa.Numeric(precision=5, scale=2), nullable=False, server_default='8.0'),
        sa.Column('is_active', sa.Boolean(), nullable=True, server_default=sa.text('1')),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('unit_label')
    )
    
    # 3. Create cold_chain_readings table
    op.create_table('cold_chain_readings',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('unit_id', sa.Integer(), nullable=False),
        sa.Column('recorded_temp_c', sa.Numeric(precision=5, scale=2), nullable=False),
        sa.Column('recorded_by_user_id', sa.Integer(), nullable=True),
        sa.Column('recorded_at', sa.DateTime(), nullable=False),
        sa.Column('note', sa.String(length=255), nullable=True),
        sa.Column('is_excursion', sa.Boolean(), nullable=False, server_default=sa.text('0')),
        sa.ForeignKeyConstraint(['recorded_by_user_id'], ['users.id'], ),
        sa.ForeignKeyConstraint(['unit_id'], ['cold_chain_units.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_cold_chain_readings_recorded_at'), 'cold_chain_readings', ['recorded_at'], unique=False)
    op.create_index(op.f('ix_cold_chain_readings_recorded_by_user_id'), 'cold_chain_readings', ['recorded_by_user_id'], unique=False)
    op.create_index(op.f('ix_cold_chain_readings_unit_id'), 'cold_chain_readings', ['unit_id'], unique=False)

    # 4. Create surveillance_daily_counts table
    op.create_table('surveillance_daily_counts',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('condition_name', sa.String(length=150), nullable=False),
        sa.Column('count_date', sa.Date(), nullable=False),
        sa.Column('otc_units', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('condition_name', 'count_date', name='uq_surveillance_daily_counts_cond_date')
    )
    op.create_index(op.f('ix_surveillance_daily_counts_condition_name'), 'surveillance_daily_counts', ['condition_name'], unique=False)
    op.create_index(op.f('ix_surveillance_daily_counts_count_date'), 'surveillance_daily_counts', ['count_date'], unique=False)


def downgrade():
    op.drop_index(op.f('ix_surveillance_daily_counts_count_date'), table_name='surveillance_daily_counts')
    op.drop_index(op.f('ix_surveillance_daily_counts_condition_name'), table_name='surveillance_daily_counts')
    op.drop_table('surveillance_daily_counts')
    
    op.drop_index(op.f('ix_cold_chain_readings_unit_id'), table_name='cold_chain_readings')
    op.drop_index(op.f('ix_cold_chain_readings_recorded_by_user_id'), table_name='cold_chain_readings')
    op.drop_index(op.f('ix_cold_chain_readings_recorded_at'), table_name='cold_chain_readings')
    op.drop_table('cold_chain_readings')
    
    op.drop_table('cold_chain_units')
    
    op.drop_column('medicine_batches', 'is_cold_chain')

