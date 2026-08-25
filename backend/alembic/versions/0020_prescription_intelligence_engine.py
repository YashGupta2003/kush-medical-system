"""Prescription Intelligence Engine — prescriptions + prescription_items tables

Revision ID: 0020
Revises: 0015
Create Date: 2026-08-25
"""
from alembic import op
import sqlalchemy as sa

# Find the current head by checking existing migration files and set this correctly
revision = '0020'
# Set down_revision to the most recent existing migration file's revision ID
# by reading the files in alembic/versions/
down_revision = '0015_trust_score_cache'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'prescriptions',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('customer_id', sa.Integer(), sa.ForeignKey('customers.id'), nullable=True),
        sa.Column('image_path', sa.String(500), nullable=False),
        sa.Column('status', sa.Enum('queued', 'processing', 'ready', 'converted', 'abandoned', name='prescription_status'), nullable=False, server_default='queued'),
        sa.Column('converted_to_sale', sa.Boolean(), nullable=False, server_default='0'),
        sa.Column('purchased_at', sa.DateTime(), nullable=True),
        sa.Column('raw_ocr_text', sa.Text(), nullable=True),
        sa.Column('ocr_confidence', sa.Numeric(5, 2), nullable=True),
        sa.Column('doctor_name', sa.String(150), nullable=True),
        sa.Column('clinic_name', sa.String(200), nullable=True),
        sa.Column('processing_error', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_prescriptions_id', 'prescriptions', ['id'])
    op.create_index('ix_prescriptions_customer_id', 'prescriptions', ['customer_id'])
    op.create_index('ix_prescriptions_status', 'prescriptions', ['status'])
    op.create_index('ix_prescriptions_created_at', 'prescriptions', ['created_at'])

    op.create_table(
        'prescription_items',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('prescription_id', sa.Integer(), sa.ForeignKey('prescriptions.id'), nullable=False),
        sa.Column('medicine_id', sa.Integer(), sa.ForeignKey('medicines.id'), nullable=True),
        sa.Column('substitute_medicine_id', sa.Integer(), sa.ForeignKey('medicines.id'), nullable=True),
        sa.Column('raw_name', sa.String(255), nullable=False),
        sa.Column('qty_prescribed', sa.Numeric(10, 2), nullable=True),
        sa.Column('dosage_instructions', sa.String(255), nullable=True),
        sa.Column('match_confidence', sa.Numeric(5, 2), nullable=True),
        sa.Column('match_status', sa.Enum('auto', 'learned', 'manual', 'unmatched', name='rx_match_status'), nullable=True, server_default='unmatched'),
        sa.Column('in_stock', sa.Boolean(), nullable=True),
        sa.Column('current_stock_qty', sa.Numeric(10, 2), nullable=True),
        sa.Column('added_to_cart', sa.Boolean(), nullable=False, server_default='0'),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_prescription_items_id', 'prescription_items', ['id'])
    op.create_index('ix_prescription_items_prescription_id', 'prescription_items', ['prescription_id'])
    op.create_index('ix_prescription_items_medicine_id', 'prescription_items', ['medicine_id'])


def downgrade():
    op.drop_table('prescription_items')
    op.drop_table('prescriptions')
    op.execute("DROP TYPE IF EXISTS prescription_status")
    op.execute("DROP TYPE IF EXISTS rx_match_status")
