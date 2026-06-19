"""Update phone regex patterns to accept local format numbers

Revision ID: update_phone_regex
Revises: 94391cd3ad69
Create Date: 2024-06-19

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'update_phone_regex'
down_revision = '94391cd3ad69'
branch_labels = None
depends_on = None


def upgrade():
    # Update phone regex patterns to accept local format numbers (without country code prefix)
    op.execute("""
        UPDATE country_rules 
        SET phone_regex = '^\\d{10}$'
        WHERE country_code = 'IN'
    """)
    
    op.execute("""
        UPDATE country_rules 
        SET phone_regex = '^\\d{10}$'
        WHERE country_code = 'US'
    """)
    
    op.execute("""
        UPDATE country_rules 
        SET phone_regex = '^\\d{8}$'
        WHERE country_code = 'SG'
    """)
    
    op.execute("""
        UPDATE country_rules 
        SET phone_regex = '^\\d{6,11}$'
        WHERE country_code = 'DE'
    """)
    
    # Add CRYPTO to payment modes for all countries
    op.execute("""
        UPDATE country_rules 
        SET valid_payment_modes = COALESCE(valid_payment_modes, '[]')::jsonb || '["CRYPTO"]'::jsonb
        WHERE is_active = true
    """)


def downgrade():
    # Revert to international format (with country code prefix)
    op.execute("""
        UPDATE country_rules 
        SET phone_regex = '^\\+91[6-9]\\d{9}$'
        WHERE country_code = 'IN'
    """)
    
    op.execute("""
        UPDATE country_rules 
        SET phone_regex = '^\\+1\\d{10}$'
        WHERE country_code = 'US'
    """)
    
    op.execute("""
        UPDATE country_rules 
        SET phone_regex = '^\\+65[3689]\\d{7}$'
        WHERE country_code = 'SG'
    """)
    
    op.execute("""
        UPDATE country_rules 
        SET phone_regex = '^\\+49\\d{6,11}$'
        WHERE country_code = 'DE'
    """)
    
    # Remove CRYPTO from payment modes
    op.execute("""
        UPDATE country_rules 
        SET valid_payment_modes = (
            SELECT jsonb_agg(elem) 
            FROM jsonb_array_elements(valid_payment_modes) elem 
            WHERE elem::text != '"CRYPTO"'
        )
        WHERE is_active = true AND valid_payment_modes IS NOT NULL
    """)
