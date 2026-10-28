"""Задачи команды: доски, колонки, метки, задачи, подзадачи, комментарии, история,
учёт времени, напоминания и цикличные серии."""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import BigInteger, Boolean, DateTime, Float, ForeignKey, Index, Integer, SmallInteger, String, Text
from sqlalchemy.dialects.postgresql import ARRAY, JSONB
from sqlalchemy.orm import Mapped, mapped_column

from bot.db.base import Base, utcnow

PRIORITY_LOW, PRIORITY_NORMAL, PRIORITY_HIGH, PRIORITY_URGENT = 0, 1, 2, 3

# Виды напоминаний.
REM_BEFORE = "before"  # за N минут до дедлайна
REM_AT = "at"  # в конкретное время
REM_REPEAT = "repeat"  # каждые N минут, пока не выполнена (с момента start_at)
REM_OVERDUE = "overdue"  # после дедлайна: сразу и далее каждые N минут (0 — один раз)
REMINDER_KINDS = (REM_BEFORE, REM_AT, REM_REPEAT, REM_OVERDUE)

# Серии (цикличные задачи).
RULE_INTERVAL = "interval"  # каждые N часов/дней
RULE_WEEKLY = "weekly"  # по дням недели в заданное время
RULE_MONTHLY = "monthly"  # каждого N-го числа в заданное время
SERIES_SCHEDULE = "schedule"  # новая копия — по расписанию, даже если прошлая не сделана
SERIES_AFTER_DONE = "after_done"  # новая копия — после выполнения прошлой (следующий слот)


class Board(Base):
    __tablename__ = "boards"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(128))
    description: Mapped[str | None] = mapped_column(Text)
    color: Mapped[str] = mapped_column(String(16), default="#5b8cff")
    position: Mapped[int] = mapped_column(Integer, default=0)
    archived: Mapped[bool] = mapped_column(Boolean, default=False)
    created_by: Mapped[int | None] = mapped_column(BigInteger)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class BoardColumn(Base):
    __tablename__ = "board_columns"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    board_id: Mapped[int] = mapped_column(Integer, ForeignKey("boards.id", ondelete="CASCADE"), index=True)
    name: Mapped[str] = mapped_column(String(64))
    position: Mapped[int] = mapped_column(Integer, default=0)
    is_done: Mapped[bool] = mapped_column(Boolean, default=False)  # перенос сюда = задача выполнена
    wip_limit: Mapped[int | None] = mapped_column(Integer)


class Label(Base):
    __tablename__ = "labels"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    board_id: Mapped[int] = mapped_column(Integer, ForeignKey("boards.id", ondelete="CASCADE"), index=True)
    name: Mapped[str] = mapped_column(String(32))
    color: Mapped[str] = mapped_column(String(16), default="#7fd4ff")


class Task(Base):
    __tablename__ = "tasks"
    __table_args__ = (Index("ix_tasks_board_column", "board_id", "column_id", "position"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    board_id: Mapped[int] = mapped_column(Integer, ForeignKey("boards.id", ondelete="CASCADE"))
    column_id: Mapped[int] = mapped_column(Integer, ForeignKey("board_columns.id", ondelete="RESTRICT"))
    title: Mapped[str] = mapped_column(String(256))
    description: Mapped[str | None] = mapped_column(Text)
    priority: Mapped[int] = mapped_column(SmallInteger, default=PRIORITY_NORMAL)
    label_ids: Mapped[list[int]] = mapped_column(ARRAY(Integer), default=list)
    start_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    deadline: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)
    deadline_hard: Mapped[bool] = mapped_column(Boolean, default=True)  # False — «мягкий» срок, ориентир
    estimate_minutes: Mapped[int | None] = mapped_column(Integer)
    position: Mapped[float] = mapped_column(Float, default=0.0)
    series_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("task_series.id", ondelete="SET NULL"), index=True)
    archived: Mapped[bool] = mapped_column(Boolean, default=False)
    created_by: Mapped[int | None] = mapped_column(BigInteger)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    completed_by: Mapped[int | None] = mapped_column(BigInteger)


class TaskAssignee(Base):
    __tablename__ = "task_assignees"

    task_id: Mapped[int] = mapped_column(Integer, ForeignKey("tasks.id", ondelete="CASCADE"), primary_key=True)
    user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("tg_users.id", ondelete="CASCADE"), primary_key=True, index=True)
    taken_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))  # нажал «Взял»
    assigned_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class ChecklistItem(Base):
    """Подзадача (пункт чек-листа), можно назначить отдельного исполнителя и срок."""

    __tablename__ = "checklist_items"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    task_id: Mapped[int] = mapped_column(Integer, ForeignKey("tasks.id", ondelete="CASCADE"), index=True)
    text: Mapped[str] = mapped_column(String(512))
    done: Mapped[bool] = mapped_column(Boolean, default=False)
    done_by: Mapped[int | None] = mapped_column(BigInteger)
    done_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    assignee_id: Mapped[int | None] = mapped_column(BigInteger)
    deadline: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    position: Mapped[int] = mapped_column(Integer, default=0)


class TaskComment(Base):
    __tablename__ = "task_comments"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    task_id: Mapped[int] = mapped_column(Integer, ForeignKey("tasks.id", ondelete="CASCADE"), index=True)
    user_id: Mapped[int] = mapped_column(BigInteger)
    text: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class TaskHistory(Base):
    __tablename__ = "task_history"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    task_id: Mapped[int] = mapped_column(Integer, ForeignKey("tasks.id", ondelete="CASCADE"), index=True)
    user_id: Mapped[int | None] = mapped_column(BigInteger)  # None — система (серия, напоминание)
    action: Mapped[str] = mapped_column(String(32))
    data: Mapped[dict] = mapped_column(JSONB, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class TimeEntry(Base):
    """Учёт времени: открытая запись (ended_at IS NULL) — таймер идёт; у человека не больше одной."""

    __tablename__ = "time_entries"
    __table_args__ = (Index("ix_time_entries_user_open", "user_id", "ended_at"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    task_id: Mapped[int] = mapped_column(Integer, ForeignKey("tasks.id", ondelete="CASCADE"), index=True)
    user_id: Mapped[int] = mapped_column(BigInteger)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    ended_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    seconds: Mapped[int | None] = mapped_column(Integer)
    note: Mapped[str | None] = mapped_column(String(256))


class TaskReminder(Base):
    __tablename__ = "task_reminders"
    __table_args__ = (Index("ix_task_reminders_due", "active", "next_at"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    task_id: Mapped[int] = mapped_column(Integer, ForeignKey("tasks.id", ondelete="CASCADE"), index=True)
    kind: Mapped[str] = mapped_column(String(16))
    offset_minutes: Mapped[int | None] = mapped_column(Integer)  # REM_BEFORE
    at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))  # REM_AT; REM_REPEAT — старт
    interval_minutes: Mapped[int | None] = mapped_column(Integer)  # REM_REPEAT / REM_OVERDUE
    text: Mapped[str | None] = mapped_column(String(512))  # своя приписка к напоминанию
    next_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    sent_count: Mapped[int] = mapped_column(Integer, default=0)
    active: Mapped[bool] = mapped_column(Boolean, default=True)


class TaskSeries(Base):
    """Цикличная задача: шаблон — последняя созданная копия (`template_task_id`)."""

    __tablename__ = "task_series"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    board_id: Mapped[int] = mapped_column(Integer, ForeignKey("boards.id", ondelete="CASCADE"))
    template_task_id: Mapped[int | None] = mapped_column(Integer)
    rule: Mapped[dict] = mapped_column(JSONB)  # {type, n, unit, weekdays, day, time}
    mode: Mapped[str] = mapped_column(String(16), default=SERIES_SCHEDULE)
    deadline_minutes: Mapped[int | None] = mapped_column(Integer)  # срок копии: через N минут после появления
    rotate: Mapped[bool] = mapped_column(Boolean, default=False)  # исполнитель по кругу из rotation
    rotation: Mapped[list[int]] = mapped_column(ARRAY(BigInteger), default=list)
    rotation_index: Mapped[int] = mapped_column(Integer, default=0)
    next_run_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)
    ends_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_by: Mapped[int | None] = mapped_column(BigInteger)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
