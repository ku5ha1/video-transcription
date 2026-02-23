"""add file_hash to videos

Revision ID: 003
Revises: 002
Create Date: 2024-02-23

"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "003"
down_revision = "002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Add file_hash column to videos table
    op.add_column("videos", sa.Column("file_hash", sa.String(length=64), nullable=True))
    op.create_index(op.f("ix_videos_file_hash"), "videos", ["file_hash"], unique=False)


def downgrade() -> None:
    # Remove file_hash column and index
    op.drop_index(op.f("ix_videos_file_hash"), table_name="videos")
    op.drop_column("videos", "file_hash")
