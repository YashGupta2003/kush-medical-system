"""Trust score cache

Revision ID: 0015_trust_score_cache
Revises: 0014_surveillance_cold_chain
Create Date: 2026-08-10 23:51:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '0015_trust_score_cache'
down_revision = '0014_surveillance_cold_chain'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'distributor_trust_scores',
        sa.Column('id', sa.Integer(), primary_key=True, index=True),
        sa.Column('distributor_id', sa.Integer(), sa.ForeignKey('distributors.id'), nullable=False, index=True),
        sa.Column('medicine_id', sa.Integer(), sa.ForeignKey('medicines.id'), nullable=True, index=True),
        sa.Column('score', sa.Numeric(5, 2), nullable=False),
        sa.Column('confidence', sa.Enum('low', 'medium', 'high', name='trust_confidence'), nullable=False),
        sa.Column('computed_at', sa.DateTime(), nullable=False),
        sa.UniqueConstraint('distributor_id', 'medicine_id', name='uq_distributor_trust_score')
    )


def downgrade():
    op.drop_table('distributor_trust_scores')
    # For postgres we might need to manually drop the custom enum type
    op.execute("DROP TYPE IF EXISTS trust_confidence;")
