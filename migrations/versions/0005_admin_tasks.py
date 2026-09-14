"""admin chats and task planner

Revision ID: 0005_admin_tasks
Revises: 0004_drop_tournament
Create Date: 2026-09-14

"""
from alembic import op
import sqlalchemy as sa

revision = "0005_admin_tasks"
down_revision = "0004_drop_tournament"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "admin_chats",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("tg_chat_id", sa.BigInteger, nullable=False, unique=True),
        sa.Column("title", sa.String(255), nullable=True),
        sa.Column("owner_user_id", sa.Integer, sa.ForeignKey("bot_users.id"), nullable=False),
        sa.Column("created_at", sa.DateTime, nullable=False, server_default=sa.func.now()),
    )

    op.create_table(
        "tasks",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column(
            "admin_chat_id", sa.Integer, sa.ForeignKey("admin_chats.id", ondelete="CASCADE"), nullable=False
        ),
        sa.Column("created_by_tg_id", sa.BigInteger, nullable=False),
        sa.Column("assignee_tg_id", sa.BigInteger, nullable=False),
        sa.Column("assignee_name", sa.String(255), nullable=True),
        sa.Column("title", sa.String(1024), nullable=False),
        sa.Column("deadline", sa.DateTime, nullable=True),
        sa.Column("reminder_policy", sa.String(32), nullable=False, server_default="none"),
        sa.Column("status", sa.String(16), nullable=False, server_default="open"),
        sa.Column("chat_message_id", sa.BigInteger, nullable=True),
        sa.Column("pre_reminder_sent", sa.Boolean, nullable=False, server_default=sa.false()),
        sa.Column("deadline_notified", sa.Boolean, nullable=False, server_default=sa.false()),
        sa.Column("last_reminded_at", sa.DateTime, nullable=True),
        sa.Column("created_at", sa.DateTime, nullable=False, server_default=sa.func.now()),
        sa.Column("completed_at", sa.DateTime, nullable=True),
    )
    op.create_index("ix_tasks_admin_chat_status", "tasks", ["admin_chat_id", "status"])
    op.create_index("ix_tasks_pending_reminder", "tasks", ["status", "deadline"])


def downgrade() -> None:
    op.drop_index("ix_tasks_pending_reminder", table_name="tasks")
    op.drop_index("ix_tasks_admin_chat_status", table_name="tasks")
    op.drop_table("tasks")
    op.drop_table("admin_chats")
