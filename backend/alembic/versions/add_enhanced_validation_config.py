"""add enhanced validation config to country_rules

Revision ID: add_enhanced_validation_config
Revises: b2e4f89c1234
Create Date: 2026-06-19
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

revision = 'add_enhanced_validation_config'
down_revision = 'b2e4f89c1234'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column('country_rules', sa.Column('valid_currencies', JSONB, nullable=True))
    op.add_column('country_rules', sa.Column('min_amount', sa.Float(), nullable=True))
    op.add_column('country_rules', sa.Column('max_amount', sa.Float(), nullable=True))
    op.add_column('country_rules', sa.Column('min_quantity', sa.Integer(), nullable=True, default=1))
    op.add_column('country_rules', sa.Column('max_quantity', sa.Integer(), nullable=True))
    op.add_column('country_rules', sa.Column('allow_future_dates', sa.Boolean(), nullable=False, default=False))
    op.add_column('country_rules', sa.Column('required_fields', JSONB, nullable=True))
    op.add_column('country_rules', sa.Column('email_domain_whitelist', JSONB, nullable=True))


def downgrade() -> None:
    op.drop_column('country_rules', 'email_domain_whitelist')
    op.drop_column('country_rules', 'required_fields')
    op.drop_column('country_rules', 'allow_future_dates')
    op.drop_column('country_rules', 'max_quantity')
    op.drop_column('country_rules', 'min_quantity')
    op.drop_column('country_rules', 'max_amount')
    op.drop_column('country_rules', 'min_amount')
    op.drop_column('country_rules', 'valid_currencies')
