"""task kinds, recurrence and admin roles

Revision ID: 0006_task_variations
Revises: 0005_admin_tasks
Create Date: 2026-09-14

"""
from alembic import op
import sqlalchemy as sa

revision = "0006_task_variations"
down_revision = "0005_admin_tasks"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("tasks", sa.Column("created_by_name", sa.String(255), nullable=True))
    op.add_column("tasks", sa.Column("recurrence", sa.String(16), nullable=False, server_default="none"))
    op.add_column("tasks", sa.Column("kind", sa.String(16), nullable=False, server_default="task"))
    op.create_index("ix_tasks_kind", "tasks", ["admin_chat_id", "kind", "status"])

    op.create_table(
        "admin_roles",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column(
            "admin_chat_id", sa.Integer, sa.ForeignKey("admin_chats.id", ondelete="CASCADE"), nullable=False
        ),
        sa.Column("tg_user_id", sa.BigInteger, nullable=False),
        sa.Column("description", sa.String(2048), nullable=False),
        sa.Column("updated_at", sa.DateTime, nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("admin_chat_id", "tg_user_id", name="uq_admin_role_user"),
    )


def downgrade() -> None:
    op.drop_table("admin_roles")
    op.drop_index("ix_tasks_kind", table_name="tasks")
    op.drop_column("tasks", "kind")
    op.drop_column("tasks", "recurrence")
    op.drop_column("tasks", "created_by_name")
