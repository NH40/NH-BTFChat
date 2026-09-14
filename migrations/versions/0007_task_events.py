"""task events for done/missed history and admin stats

Revision ID: 0007_task_events
Revises: 0006_task_variations
Create Date: 2026-09-14

"""
from alembic import op
import sqlalchemy as sa

revision = "0007_task_events"
down_revision = "0006_task_variations"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "task_events",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column(
            "admin_chat_id", sa.Integer, sa.ForeignKey("admin_chats.id", ondelete="CASCADE"), nullable=False
        ),
        sa.Column("task_id", sa.Integer, sa.ForeignKey("tasks.id", ondelete="CASCADE"), nullable=False),
        sa.Column("assignee_tg_id", sa.BigInteger, nullable=False),
        sa.Column("assignee_name", sa.String(255), nullable=True),
        sa.Column("event", sa.String(16), nullable=False),
        sa.Column("on_time", sa.Boolean, nullable=True),
        sa.Column("deadline", sa.DateTime, nullable=True),
        sa.Column("created_at", sa.DateTime, nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_task_events_admin_chat", "task_events", ["admin_chat_id", "event"])


def downgrade() -> None:
    op.drop_index("ix_task_events_admin_chat", table_name="task_events")
    op.drop_table("task_events")
