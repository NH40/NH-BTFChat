"""init

Revision ID: 0001_init
Revises:
Create Date: 2026-08-28

"""
from alembic import op
import sqlalchemy as sa

revision = "0001_init"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "bot_users",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("tg_user_id", sa.BigInteger, nullable=False, unique=True),
        sa.Column("username", sa.String(255), nullable=True),
        sa.Column("created_at", sa.DateTime, nullable=False, server_default=sa.func.now()),
    )

    op.create_table(
        "channels",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("tg_chat_id", sa.BigInteger, nullable=False, unique=True),
        sa.Column("username", sa.String(255), nullable=True),
        sa.Column("title", sa.String(255), nullable=True),
        sa.Column("bot_is_admin", sa.Boolean, nullable=False, server_default=sa.false()),
        sa.Column("owner_user_id", sa.Integer, sa.ForeignKey("bot_users.id"), nullable=False),
        sa.Column("created_at", sa.DateTime, nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime, nullable=False, server_default=sa.func.now()),
    )

    op.create_table(
        "target_chats",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("tg_chat_id", sa.BigInteger, nullable=False, unique=True),
        sa.Column("title", sa.String(255), nullable=True),
        sa.Column("chat_type", sa.String(32), nullable=False),
        sa.Column("owner_user_id", sa.Integer, sa.ForeignKey("bot_users.id"), nullable=False),
        sa.Column("created_at", sa.DateTime, nullable=False, server_default=sa.func.now()),
    )

    op.create_table(
        "subscriptions",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("owner_user_id", sa.Integer, sa.ForeignKey("bot_users.id"), nullable=False),
        sa.Column("channel_id", sa.Integer, sa.ForeignKey("channels.id"), nullable=False),
        sa.Column("target_chat_id", sa.Integer, sa.ForeignKey("target_chats.id"), nullable=False),
        sa.Column("created_at", sa.DateTime, nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("channel_id", "target_chat_id", name="uq_channel_target"),
    )

    op.create_table(
        "pending_actions",
        sa.Column("tg_user_id", sa.BigInteger, primary_key=True),
        sa.Column("action", sa.String(64), nullable=False),
        sa.Column("payload", sa.JSON, nullable=False, server_default="{}"),
        sa.Column("created_at", sa.DateTime, nullable=False, server_default=sa.func.now()),
    )


def downgrade() -> None:
    op.drop_table("pending_actions")
    op.drop_table("subscriptions")
    op.drop_table("target_chats")
    op.drop_table("channels")
    op.drop_table("bot_users")
