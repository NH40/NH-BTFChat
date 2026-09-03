"""post tracking for edits and deletions

Revision ID: 0002_post_tracking
Revises: 0001_init
Create Date: 2026-09-03

"""
from alembic import op
import sqlalchemy as sa

revision = "0002_post_tracking"
down_revision = "0001_init"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "source_posts",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column(
            "channel_id", sa.Integer, sa.ForeignKey("channels.id", ondelete="CASCADE"), nullable=False
        ),
        sa.Column("source_message_id", sa.BigInteger, nullable=False),
        sa.Column("media_group_id", sa.String(64), nullable=True),
        sa.Column("is_deleted", sa.Boolean, nullable=False, server_default=sa.false()),
        sa.Column("created_at", sa.DateTime, nullable=False, server_default=sa.func.now()),
        sa.Column("last_checked_at", sa.DateTime, nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("channel_id", "source_message_id", name="uq_channel_message"),
    )
    op.create_index("ix_source_posts_pending", "source_posts", ["is_deleted", "created_at"])

    op.create_table(
        "post_copies",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column(
            "source_post_id",
            sa.Integer,
            sa.ForeignKey("source_posts.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("target_chat_tg_id", sa.BigInteger, nullable=False),
        sa.Column("target_message_id", sa.BigInteger, nullable=False),
        sa.Column("is_signature", sa.Boolean, nullable=False, server_default=sa.false()),
        sa.Column("created_at", sa.DateTime, nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_post_copies_source_post_id", "post_copies", ["source_post_id"])


def downgrade() -> None:
    op.drop_index("ix_post_copies_source_post_id", table_name="post_copies")
    op.drop_table("post_copies")
    op.drop_index("ix_source_posts_pending", table_name="source_posts")
    op.drop_table("source_posts")
