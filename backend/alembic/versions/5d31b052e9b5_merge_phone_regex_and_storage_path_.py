"""merge phone regex and storage path migrations

Revision ID: 5d31b052e9b5
Revises: rename_file_path_to_storage_path, update_phone_regex
Create Date: 2026-06-19 09:00:49.219829

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '5d31b052e9b5'
down_revision: Union[str, Sequence[str], None] = ('rename_file_path_to_storage_path', 'update_phone_regex')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
