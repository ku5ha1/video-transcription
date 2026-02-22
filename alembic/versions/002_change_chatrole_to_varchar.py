"""Change chat_messages.role from ENUM to VARCHAR

Revision ID: 002
Revises: 001
Create Date: 2026-02-22

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = '002'
down_revision = '001'
branch_labels = None
depends_on = None


def upgrade():
    # Change role column from ENUM to VARCHAR
    op.execute("ALTER TABLE chat_messages ALTER COLUMN role TYPE VARCHAR(50)")
    
    # Drop the ENUM type if it exists
    op.execute("DROP TYPE IF EXISTS chatrole")


def downgrade():
    # Recreate ENUM type
    op.execute("CREATE TYPE chatrole AS ENUM ('user', 'assistant')")
    
    # Change role column back to ENUM
    op.execute("ALTER TABLE chat_messages ALTER COLUMN role TYPE chatrole USING role::chatrole")
