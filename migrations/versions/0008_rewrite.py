"""BTF 2.0: новая схема (модерация, пересылка, задачи команды) + перенос старых данных.

Старые таблицы не удаляются — переименовываются в legacy_* (вместе с их индексами и
последовательностями, иначе `tasks_pkey`/`tasks_id_seq` столкнулись бы с новой таблицей `tasks`).

Revision ID: 0008_rewrite
Revises: 0007_task_events
Create Date: 2026-10-28
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import ARRAY, JSONB

revision = "0008_rewrite"
down_revision = "0007_task_events"
branch_labels = None
depends_on = None

LEGACY = (
    "pending_actions", "admin_roles", "task_events", "tasks", "admin_chats", "post_copies",
    "source_posts", "subscriptions", "target_chats", "channels", "bot_users",
)

TS = sa.DateTime(timezone=True)


def _now():
    return sa.text("now()")


def upgrade() -> None:
    bind = op.get_bind()
    existing = set(sa.inspect(bind).get_table_names())
    legacy = [t for t in LEGACY if t in existing]

    # 1. Индексы/ограничения и последовательности старых таблиц — с префиксом legacy_.
    for table in legacy:
        op.execute(f"""
        DO $$ DECLARE r record; BEGIN
          FOR r IN SELECT indexname FROM pg_indexes WHERE schemaname = 'public' AND tablename = '{table}' LOOP
            EXECUTE format('ALTER INDEX %I RENAME TO %I', r.indexname, left('legacy_' || r.indexname, 63));
          END LOOP;
          FOR r IN SELECT c.relname FROM pg_class c JOIN pg_depend d ON d.objid = c.oid
                   JOIN pg_class t ON t.oid = d.refobjid
                   WHERE c.relkind = 'S' AND t.relname = '{table}' LOOP
            EXECUTE format('ALTER SEQUENCE %I RENAME TO %I', r.relname, left('legacy_' || r.relname, 63));
          END LOOP;
        END $$;
        """)
        op.rename_table(table, f"legacy_{table}")

    # 2. Новая схема.
    op.create_table(
        "tg_users",
        sa.Column("id", sa.BigInteger, primary_key=True),
        sa.Column("username", sa.String(64)),
        sa.Column("first_name", sa.String(128)),
        sa.Column("last_name", sa.String(128)),
        sa.Column("created_at", TS, server_default=_now(), nullable=False),
        sa.Column("last_seen_at", TS, server_default=_now(), nullable=False),
    )
    op.create_index("ix_tg_users_username", "tg_users", ["username"])
    op.create_table(
        "staff",
        sa.Column("user_id", sa.BigInteger, sa.ForeignKey("tg_users.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("role", sa.String(16), nullable=False, server_default="admin"),
        sa.Column("title", sa.String(128)),
        sa.Column("notes", sa.Text),
        sa.Column("active", sa.Boolean, nullable=False, server_default=sa.true()),
        sa.Column("created_at", TS, server_default=_now(), nullable=False),
    )
    op.create_table(
        "chats",
        sa.Column("id", sa.BigInteger, primary_key=True),
        sa.Column("title", sa.String(255)),
        sa.Column("username", sa.String(64)),
        sa.Column("type", sa.String(16), nullable=False),
        sa.Column("kind", sa.String(16), nullable=False, server_default="none"),
        sa.Column("bot_status", sa.String(16), nullable=False, server_default="member"),
        sa.Column("settings", JSONB, nullable=False, server_default="{}"),
        sa.Column("created_at", TS, server_default=_now(), nullable=False),
        sa.Column("updated_at", TS, server_default=_now(), nullable=False),
    )
    op.create_table(
        "app_settings",
        sa.Column("key", sa.String(64), primary_key=True),
        sa.Column("value", JSONB, nullable=False, server_default="{}"),
    )
    op.create_table(
        "chat_warnings",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("chat_id", sa.BigInteger, sa.ForeignKey("chats.id", ondelete="CASCADE"), nullable=False),
        sa.Column("user_id", sa.BigInteger, nullable=False),
        sa.Column("reason", sa.Text),
        sa.Column("issued_by", sa.BigInteger),
        sa.Column("active", sa.Boolean, nullable=False, server_default=sa.true()),
        sa.Column("created_at", TS, server_default=_now(), nullable=False),
    )
    op.create_index("ix_warnings_chat_user", "chat_warnings", ["chat_id", "user_id"])
    op.create_table(
        "mod_actions",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("chat_id", sa.BigInteger, sa.ForeignKey("chats.id", ondelete="CASCADE"), nullable=False),
        sa.Column("target_id", sa.BigInteger, nullable=False),
        sa.Column("actor_id", sa.BigInteger),
        sa.Column("action", sa.String(16), nullable=False),
        sa.Column("reason", sa.Text),
        sa.Column("until", TS),
        sa.Column("created_at", TS, server_default=_now(), nullable=False),
    )
    op.create_index("ix_mod_actions_chat_created", "mod_actions", ["chat_id", "created_at"])
    op.create_index("ix_mod_actions_target_id", "mod_actions", ["target_id"])
    op.create_table(
        "relay_routes",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("channel_id", sa.BigInteger, sa.ForeignKey("chats.id", ondelete="CASCADE"), nullable=False),
        sa.Column("target_chat_id", sa.BigInteger, sa.ForeignKey("chats.id", ondelete="CASCADE"), nullable=False),
        sa.Column("active", sa.Boolean, nullable=False, server_default=sa.true()),
        sa.Column("created_at", TS, server_default=_now(), nullable=False),
        sa.UniqueConstraint("channel_id", "target_chat_id", name="uq_relay_route"),
    )
    op.create_index("ix_relay_routes_channel_id", "relay_routes", ["channel_id"])
    op.create_index("ix_relay_routes_target_chat_id", "relay_routes", ["target_chat_id"])
    op.create_table(
        "relay_posts",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("channel_id", sa.BigInteger, sa.ForeignKey("chats.id", ondelete="CASCADE"), nullable=False),
        sa.Column("message_id", sa.BigInteger, nullable=False),
        sa.Column("message_ids", ARRAY(sa.BigInteger), nullable=False),
        sa.Column("media_group_id", sa.String(64)),
        sa.Column("version", sa.Integer, nullable=False, server_default="1"),
        sa.Column("deleted", sa.Boolean, nullable=False, server_default=sa.false()),
        sa.Column("created_at", TS, server_default=_now(), nullable=False),
        sa.Column("last_checked_at", TS, server_default=_now(), nullable=False),
        sa.UniqueConstraint("channel_id", "message_id", name="uq_relay_post"),
    )
    op.create_index("ix_relay_posts_check", "relay_posts", ["deleted", "last_checked_at"])
    op.create_table(
        "relay_copies",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("post_id", sa.Integer, sa.ForeignKey("relay_posts.id", ondelete="CASCADE"), nullable=False),
        sa.Column("target_chat_id", sa.BigInteger, nullable=False),
        sa.Column("message_ids", ARRAY(sa.BigInteger), nullable=False),
        sa.Column("version", sa.Integer, nullable=False, server_default="1"),
        sa.Column("created_at", TS, server_default=_now(), nullable=False),
    )
    op.create_index("ix_relay_copies_post_id", "relay_copies", ["post_id"])
    op.create_table(
        "boards",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("name", sa.String(128), nullable=False),
        sa.Column("description", sa.Text),
        sa.Column("color", sa.String(16), nullable=False, server_default="#5b8cff"),
        sa.Column("position", sa.Integer, nullable=False, server_default="0"),
        sa.Column("archived", sa.Boolean, nullable=False, server_default=sa.false()),
        sa.Column("created_by", sa.BigInteger),
        sa.Column("created_at", TS, server_default=_now(), nullable=False),
    )
    op.create_table(
        "board_columns",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("board_id", sa.Integer, sa.ForeignKey("boards.id", ondelete="CASCADE"), nullable=False),
        sa.Column("name", sa.String(64), nullable=False),
        sa.Column("position", sa.Integer, nullable=False, server_default="0"),
        sa.Column("is_done", sa.Boolean, nullable=False, server_default=sa.false()),
        sa.Column("wip_limit", sa.Integer),
    )
    op.create_index("ix_board_columns_board_id", "board_columns", ["board_id"])
    op.create_table(
        "labels",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("board_id", sa.Integer, sa.ForeignKey("boards.id", ondelete="CASCADE"), nullable=False),
        sa.Column("name", sa.String(32), nullable=False),
        sa.Column("color", sa.String(16), nullable=False, server_default="#7fd4ff"),
    )
    op.create_index("ix_labels_board_id", "labels", ["board_id"])
    op.create_table(
        "task_series",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("board_id", sa.Integer, sa.ForeignKey("boards.id", ondelete="CASCADE"), nullable=False),
        sa.Column("template_task_id", sa.Integer),
        sa.Column("rule", JSONB, nullable=False),
        sa.Column("mode", sa.String(16), nullable=False, server_default="schedule"),
        sa.Column("deadline_minutes", sa.Integer),
        sa.Column("rotate", sa.Boolean, nullable=False, server_default=sa.false()),
        sa.Column("rotation", ARRAY(sa.BigInteger), nullable=False, server_default="{}"),
        sa.Column("rotation_index", sa.Integer, nullable=False, server_default="0"),
        sa.Column("next_run_at", TS),
        sa.Column("ends_at", TS),
        sa.Column("active", sa.Boolean, nullable=False, server_default=sa.true()),
        sa.Column("created_by", sa.BigInteger),
        sa.Column("created_at", TS, server_default=_now(), nullable=False),
    )
    op.create_index("ix_task_series_next_run_at", "task_series", ["next_run_at"])
    op.create_table(
        "tasks",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("board_id", sa.Integer, sa.ForeignKey("boards.id", ondelete="CASCADE"), nullable=False),
        sa.Column("column_id", sa.Integer, sa.ForeignKey("board_columns.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("title", sa.String(256), nullable=False),
        sa.Column("description", sa.Text),
        sa.Column("priority", sa.SmallInteger, nullable=False, server_default="1"),
        sa.Column("label_ids", ARRAY(sa.Integer), nullable=False, server_default="{}"),
        sa.Column("start_at", TS),
        sa.Column("deadline", TS),
        sa.Column("deadline_hard", sa.Boolean, nullable=False, server_default=sa.true()),
        sa.Column("estimate_minutes", sa.Integer),
        sa.Column("position", sa.Float, nullable=False, server_default="0"),
        sa.Column("series_id", sa.Integer, sa.ForeignKey("task_series.id", ondelete="SET NULL")),
        sa.Column("archived", sa.Boolean, nullable=False, server_default=sa.false()),
        sa.Column("created_by", sa.BigInteger),
        sa.Column("created_at", TS, server_default=_now(), nullable=False),
        sa.Column("updated_at", TS, server_default=_now(), nullable=False),
        sa.Column("completed_at", TS),
        sa.Column("completed_by", sa.BigInteger),
    )
    op.create_index("ix_tasks_board_column", "tasks", ["board_id", "column_id", "position"])
    op.create_index("ix_tasks_deadline", "tasks", ["deadline"])
    op.create_index("ix_tasks_series_id", "tasks", ["series_id"])
    op.create_table(
        "task_assignees",
        sa.Column("task_id", sa.Integer, sa.ForeignKey("tasks.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("user_id", sa.BigInteger, sa.ForeignKey("tg_users.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("taken_at", TS),
        sa.Column("assigned_at", TS, server_default=_now(), nullable=False),
    )
    op.create_index("ix_task_assignees_user_id", "task_assignees", ["user_id"])
    op.create_table(
        "checklist_items",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("task_id", sa.Integer, sa.ForeignKey("tasks.id", ondelete="CASCADE"), nullable=False),
        sa.Column("text", sa.String(512), nullable=False),
        sa.Column("done", sa.Boolean, nullable=False, server_default=sa.false()),
        sa.Column("done_by", sa.BigInteger),
        sa.Column("done_at", TS),
        sa.Column("assignee_id", sa.BigInteger),
        sa.Column("deadline", TS),
        sa.Column("position", sa.Integer, nullable=False, server_default="0"),
    )
    op.create_index("ix_checklist_items_task_id", "checklist_items", ["task_id"])
    op.create_table(
        "task_comments",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("task_id", sa.Integer, sa.ForeignKey("tasks.id", ondelete="CASCADE"), nullable=False),
        sa.Column("user_id", sa.BigInteger, nullable=False),
        sa.Column("text", sa.Text, nullable=False),
        sa.Column("created_at", TS, server_default=_now(), nullable=False),
    )
    op.create_index("ix_task_comments_task_id", "task_comments", ["task_id"])
    op.create_table(
        "task_history",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("task_id", sa.Integer, sa.ForeignKey("tasks.id", ondelete="CASCADE"), nullable=False),
        sa.Column("user_id", sa.BigInteger),
        sa.Column("action", sa.String(32), nullable=False),
        sa.Column("data", JSONB, nullable=False, server_default="{}"),
        sa.Column("created_at", TS, server_default=_now(), nullable=False),
    )
    op.create_index("ix_task_history_task_id", "task_history", ["task_id"])
    op.create_table(
        "time_entries",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("task_id", sa.Integer, sa.ForeignKey("tasks.id", ondelete="CASCADE"), nullable=False),
        sa.Column("user_id", sa.BigInteger, nullable=False),
        sa.Column("started_at", TS, server_default=_now(), nullable=False),
        sa.Column("ended_at", TS),
        sa.Column("seconds", sa.Integer),
        sa.Column("note", sa.String(256)),
    )
    op.create_index("ix_time_entries_task_id", "time_entries", ["task_id"])
    op.create_index("ix_time_entries_user_open", "time_entries", ["user_id", "ended_at"])
    op.create_table(
        "task_reminders",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("task_id", sa.Integer, sa.ForeignKey("tasks.id", ondelete="CASCADE"), nullable=False),
        sa.Column("kind", sa.String(16), nullable=False),
        sa.Column("offset_minutes", sa.Integer),
        sa.Column("at", TS),
        sa.Column("interval_minutes", sa.Integer),
        sa.Column("text", sa.String(512)),
        sa.Column("next_at", TS),
        sa.Column("last_sent_at", TS),
        sa.Column("sent_count", sa.Integer, nullable=False, server_default="0"),
        sa.Column("active", sa.Boolean, nullable=False, server_default=sa.true()),
    )
    op.create_index("ix_task_reminders_task_id", "task_reminders", ["task_id"])
    op.create_index("ix_task_reminders_due", "task_reminders", ["active", "next_at"])

    # 3. Перенос данных из старой версии.
    if "bot_users" in legacy:
        op.execute("""
            INSERT INTO tg_users (id, username) SELECT tg_user_id, username FROM legacy_bot_users
            ON CONFLICT (id) DO NOTHING
        """)
    if "channels" in legacy:
        op.execute("""
            INSERT INTO chats (id, title, username, type, kind, bot_status)
            SELECT tg_chat_id, title, username, 'channel', 'channel',
                   CASE WHEN bot_is_admin THEN 'administrator' ELSE 'member' END
            FROM legacy_channels ON CONFLICT (id) DO NOTHING
        """)
    if "target_chats" in legacy:
        op.execute("""
            INSERT INTO chats (id, title, type, kind)
            SELECT tg_chat_id, title, chat_type, 'community' FROM legacy_target_chats
            ON CONFLICT (id) DO NOTHING
        """)
    if "subscriptions" in legacy:
        op.execute("""
            INSERT INTO relay_routes (channel_id, target_chat_id)
            SELECT c.tg_chat_id, t.tg_chat_id FROM legacy_subscriptions s
            JOIN legacy_channels c ON c.id = s.channel_id
            JOIN legacy_target_chats t ON t.id = s.target_chat_id
            ON CONFLICT DO NOTHING
        """)
    if "source_posts" in legacy and "post_copies" in legacy and "channels" in legacy:
        # Свежие посты (последние 72 ч) — чтобы правка/удаление в канале сработали и для уже
        # пересланного старой версией. Альбом (общий media_group_id) — один пост; копии,
        # включая старую «подпись», — одна запись на чат.
        op.execute("""
            INSERT INTO relay_posts (channel_id, message_id, message_ids, media_group_id, created_at)
            SELECT c.tg_chat_id, min(sp.source_message_id),
                   array_agg(sp.source_message_id ORDER BY sp.source_message_id),
                   max(sp.media_group_id), min(sp.created_at) AT TIME ZONE 'UTC'
            FROM legacy_source_posts sp JOIN legacy_channels c ON c.id = sp.channel_id
            WHERE NOT sp.is_deleted AND sp.created_at > (now() AT TIME ZONE 'UTC') - interval '72 hours'
            GROUP BY c.tg_chat_id, coalesce(sp.media_group_id, 'm' || sp.source_message_id)
            ON CONFLICT DO NOTHING
        """)
        op.execute("""
            INSERT INTO relay_copies (post_id, target_chat_id, message_ids)
            SELECT rp.id, pc.target_chat_tg_id, array_agg(pc.target_message_id ORDER BY pc.target_message_id)
            FROM legacy_post_copies pc
            JOIN legacy_source_posts sp ON sp.id = pc.source_post_id
            JOIN legacy_channels c ON c.id = sp.channel_id
            JOIN relay_posts rp ON rp.channel_id = c.tg_chat_id AND sp.source_message_id = ANY(rp.message_ids)
            GROUP BY rp.id, pc.target_chat_tg_id
        """)
    if "admin_chats" in legacy:
        op.execute("""
            INSERT INTO chats (id, title, type, kind)
            SELECT tg_chat_id, title, 'supergroup', 'admin' FROM legacy_admin_chats
            ON CONFLICT (id) DO UPDATE SET kind = 'admin'
        """)
        op.execute("""
            INSERT INTO app_settings (key, value)
            SELECT 'admin_chat', jsonb_build_object('chat_id', tg_chat_id) FROM legacy_admin_chats
            ORDER BY id LIMIT 1
            ON CONFLICT (key) DO NOTHING
        """)
    if "admin_roles" in legacy:
        op.execute("""
            INSERT INTO tg_users (id) SELECT DISTINCT tg_user_id FROM legacy_admin_roles ON CONFLICT DO NOTHING
        """)
        op.execute("""
            INSERT INTO staff (user_id, role, notes)
            SELECT DISTINCT ON (tg_user_id) tg_user_id, 'admin', description FROM legacy_admin_roles
            ORDER BY tg_user_id, updated_at DESC
            ON CONFLICT (user_id) DO NOTHING
        """)
    if "tasks" in legacy:
        # Доска по умолчанию + перенос задач (открытые — «В работе», выполненные — «Готово»).
        # asyncpg: по одной команде на execute.
        op.execute("INSERT INTO boards (id, name, position) VALUES (1, 'Основная', 0)")
        op.execute("""
            INSERT INTO board_columns (board_id, name, position, is_done) VALUES
              (1, 'Бэклог', 0, false), (1, 'В работе', 1, false), (1, 'На проверке', 2, false), (1, 'Готово', 3, true)
        """)
        op.execute("SELECT setval(pg_get_serial_sequence('boards', 'id'), 1)")
        op.execute("""
            INSERT INTO tg_users (id, first_name) SELECT DISTINCT ON (assignee_tg_id) assignee_tg_id, assignee_name
            FROM legacy_tasks ORDER BY assignee_tg_id ON CONFLICT DO NOTHING
        """)
        op.execute("""
            INSERT INTO tasks (board_id, column_id, title, deadline, created_at, completed_at, position)
            SELECT 1,
                   (SELECT id FROM board_columns WHERE board_id = 1 AND name =
                        CASE WHEN lt.status = 'open' THEN 'В работе' ELSE 'Готово' END),
                   left(lt.title, 256),
                   lt.deadline AT TIME ZONE 'UTC', lt.created_at AT TIME ZONE 'UTC',
                   lt.completed_at AT TIME ZONE 'UTC', lt.id
            FROM legacy_tasks lt
        """)
        # Исполнители старых задач — это и есть команда: доступ к Mini App с ролью «админ».
        op.execute("""
            INSERT INTO staff (user_id, role) SELECT DISTINCT assignee_tg_id, 'admin' FROM legacy_tasks
            ON CONFLICT (user_id) DO NOTHING
        """)
        op.execute("""
            INSERT INTO task_assignees (task_id, user_id)
            SELECT t.id, lt.assignee_tg_id FROM legacy_tasks lt
            JOIN tasks t ON t.board_id = 1 AND t.position = lt.id
            ON CONFLICT DO NOTHING
        """)


def downgrade() -> None:
    raise NotImplementedError("BTF 2.0: откат схемы не поддерживается (старые данные лежат в legacy_*)")
