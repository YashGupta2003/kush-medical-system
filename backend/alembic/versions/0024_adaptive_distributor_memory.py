"""adaptive_distributor_memory

Revision ID: 0024
Revises: 0023
Create Date: 2026-09-08

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '0024'
down_revision: Union[str, None] = '0023'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. distributor_bill_templates
    op.create_table(
        'distributor_bill_templates',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('tenant_id', sa.Integer(), nullable=False),
        sa.Column('distributor_id', sa.Integer(), nullable=False),
        sa.Column('header_signature', sa.Text(), nullable=False),
        sa.Column('column_field_map', sa.Text(), nullable=False),
        sa.Column('sample_count', sa.Integer(), server_default='1', nullable=False),
        sa.Column('last_confirmed_at', sa.DateTime(), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('now()'), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['distributor_id'], ['distributors.id'], ),
        sa.ForeignKeyConstraint(['tenant_id'], ['tenants.id'], ),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('tenant_id', 'distributor_id', name='uq_tenant_distributor_template')
    )
    op.create_index(op.f('ix_distributor_bill_templates_distributor_id'), 'distributor_bill_templates', ['distributor_id'], unique=False)
    op.create_index(op.f('ix_distributor_bill_templates_tenant_id'), 'distributor_bill_templates', ['tenant_id'], unique=False)

    # 2. distributor_field_accuracy
    op.create_table(
        'distributor_field_accuracy',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('tenant_id', sa.Integer(), nullable=False),
        sa.Column('distributor_id', sa.Integer(), nullable=False),
        sa.Column('field_name', sa.String(length=50), nullable=False),
        sa.Column('times_total', sa.Integer(), server_default='0', nullable=False),
        sa.Column('times_corrected', sa.Integer(), server_default='0', nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['distributor_id'], ['distributors.id'], ),
        sa.ForeignKeyConstraint(['tenant_id'], ['tenants.id'], ),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('tenant_id', 'distributor_id', 'field_name', name='uq_tenant_distributor_field_accuracy')
    )
    op.create_index(op.f('ix_distributor_field_accuracy_distributor_id'), 'distributor_field_accuracy', ['distributor_id'], unique=False)
    op.create_index(op.f('ix_distributor_field_accuracy_tenant_id'), 'distributor_field_accuracy', ['tenant_id'], unique=False)

    # 3. Modify bills table to add detected_header_tokens
    op.add_column('bills', sa.Column('detected_header_tokens', sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column('bills', 'detected_header_tokens')
    op.drop_index(op.f('ix_distributor_field_accuracy_tenant_id'), table_name='distributor_field_accuracy')
    op.drop_index(op.f('ix_distributor_field_accuracy_distributor_id'), table_name='distributor_field_accuracy')
    op.drop_table('distributor_field_accuracy')
    op.drop_index(op.f('ix_distributor_bill_templates_tenant_id'), table_name='distributor_bill_templates')
    op.drop_index(op.f('ix_distributor_bill_templates_distributor_id'), table_name='distributor_bill_templates')
    op.drop_table('distributor_bill_templates')
