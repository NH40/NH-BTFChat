"""Доски, колонки и метки. Создание/правка — старшие, удаление доски — владелец."""
from __future__ import annotations

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from api.deps import Viewer, bad, get_session, not_found, owner, senior, viewer
from bot.db import Board, BoardColumn, Label, Task
from bot.services import tasks

router = APIRouter(prefix="/api", tags=["boards"])


def _column_out(c: BoardColumn, counts: dict[int, int]) -> dict:
    return {"id": c.id, "name": c.name, "position": c.position, "is_done": c.is_done, "wip_limit": c.wip_limit,
            "open_count": counts.get(c.id, 0)}


@router.get("/boards")
async def list_boards(archived: bool = False, v: Viewer = Depends(viewer), session: AsyncSession = Depends(get_session)):
    boards = list(await session.scalars(select(Board).where(Board.archived.is_(archived)).order_by(Board.position, Board.id)))
    ids = [b.id for b in boards]
    if not ids:
        return []
    cols = list(await session.scalars(select(BoardColumn).where(BoardColumn.board_id.in_(ids)).order_by(BoardColumn.position)))
    labels = list(await session.scalars(select(Label).where(Label.board_id.in_(ids)).order_by(Label.id)))
    counts = dict((await session.execute(
        select(Task.column_id, func.count()).where(Task.board_id.in_(ids), Task.archived.is_(False), Task.completed_at.is_(None))
        .group_by(Task.column_id))).all())
    return [{
        "id": b.id, "name": b.name, "description": b.description, "color": b.color, "archived": b.archived,
        "columns": [_column_out(c, counts) for c in cols if c.board_id == b.id],
        "labels": [{"id": lb.id, "name": lb.name, "color": lb.color} for lb in labels if lb.board_id == b.id],
        "open_count": sum(counts.get(c.id, 0) for c in cols if c.board_id == b.id),
    } for b in boards]


class BoardIn(BaseModel):
    name: str = Field(min_length=1, max_length=128)
    color: str = Field("#5b8cff", max_length=16)
    description: str | None = None


@router.post("/boards")
async def create_board(body: BoardIn, v: Viewer = Depends(senior), session: AsyncSession = Depends(get_session)):
    board = await tasks.create_board(session, body.name, v.id, body.color)
    board.description = body.description
    await session.commit()
    return {"id": board.id}


class BoardPatch(BaseModel):
    name: str | None = Field(None, max_length=128)
    color: str | None = Field(None, max_length=16)
    description: str | None = None
    archived: bool | None = None


@router.patch("/boards/{board_id}")
async def patch_board(board_id: int, body: BoardPatch, v: Viewer = Depends(senior), session: AsyncSession = Depends(get_session)):
    board = await session.get(Board, board_id)
    if board is None:
        raise not_found("Доска не найдена")
    for key, value in body.model_dump(exclude_unset=True).items():
        if key == "name" and not (value or "").strip():
            raise bad("Пустое название")
        setattr(board, key, value)
    await session.commit()
    return {"ok": True}


@router.delete("/boards/{board_id}")
async def delete_board(board_id: int, v: Viewer = Depends(owner), session: AsyncSession = Depends(get_session)):
    board = await session.get(Board, board_id)
    if board is None:
        raise not_found("Доска не найдена")
    if int(await session.scalar(select(func.count()).select_from(Board).where(Board.archived.is_(False))) or 0) <= 1 and not board.archived:
        raise bad("Нельзя удалить единственную доску")
    # Сначала задачи: tasks.column_id → RESTRICT, каскад доски на колонки иначе упрётся в задачи.
    await session.execute(delete(Task).where(Task.board_id == board_id))
    await session.delete(board)
    await session.commit()
    return {"ok": True}


# ---------------------------------------------------------------- колонки

class ColumnIn(BaseModel):
    name: str = Field(min_length=1, max_length=64)
    is_done: bool = False
    wip_limit: int | None = None


@router.post("/boards/{board_id}/columns")
async def add_column(board_id: int, body: ColumnIn, v: Viewer = Depends(senior), session: AsyncSession = Depends(get_session)):
    if await session.get(Board, board_id) is None:
        raise not_found("Доска не найдена")
    pos = int(await session.scalar(select(func.coalesce(func.max(BoardColumn.position), -1)).where(BoardColumn.board_id == board_id)) or -1) + 1
    col = BoardColumn(board_id=board_id, name=body.name.strip(), is_done=body.is_done, wip_limit=body.wip_limit, position=pos)
    session.add(col)
    await session.commit()
    return {"id": col.id}


class ColumnPatch(BaseModel):
    name: str | None = Field(None, max_length=64)
    is_done: bool | None = None
    wip_limit: int | None = None


@router.patch("/columns/{column_id}")
async def patch_column(column_id: int, body: ColumnPatch, v: Viewer = Depends(senior), session: AsyncSession = Depends(get_session)):
    col = await session.get(BoardColumn, column_id)
    if col is None:
        raise not_found("Колонка не найдена")
    for key, value in body.model_dump(exclude_unset=True).items():
        if key == "name" and not (value or "").strip():
            raise bad("Пустое название")
        setattr(col, key, value)
    await session.commit()
    return {"ok": True}


@router.delete("/columns/{column_id}")
async def delete_column(column_id: int, v: Viewer = Depends(senior), session: AsyncSession = Depends(get_session)):
    col = await session.get(BoardColumn, column_id)
    if col is None:
        raise not_found("Колонка не найдена")
    await tasks.delete_column(session, col)
    await session.commit()
    return {"ok": True}


class OrderIn(BaseModel):
    ids: list[int]


@router.put("/boards/{board_id}/columns/order")
async def order_columns(board_id: int, body: OrderIn, v: Viewer = Depends(senior), session: AsyncSession = Depends(get_session)):
    cols = {c.id: c for c in await tasks.columns(session, board_id)}
    if set(body.ids) != set(cols):
        raise bad("Список колонок не совпадает с доской")
    for i, cid in enumerate(body.ids):
        cols[cid].position = i
    await session.commit()
    return {"ok": True}


# ---------------------------------------------------------------- метки

class LabelIn(BaseModel):
    name: str = Field(min_length=1, max_length=32)
    color: str = Field("#7fd4ff", max_length=16)


@router.post("/boards/{board_id}/labels")
async def add_label(board_id: int, body: LabelIn, v: Viewer = Depends(senior), session: AsyncSession = Depends(get_session)):
    if await session.get(Board, board_id) is None:
        raise not_found("Доска не найдена")
    label = Label(board_id=board_id, name=body.name.strip(), color=body.color)
    session.add(label)
    await session.commit()
    return {"id": label.id}


@router.patch("/labels/{label_id}")
async def patch_label(label_id: int, body: LabelIn, v: Viewer = Depends(senior), session: AsyncSession = Depends(get_session)):
    label = await session.get(Label, label_id)
    if label is None:
        raise not_found("Метка не найдена")
    label.name, label.color = body.name.strip(), body.color
    await session.commit()
    return {"ok": True}


@router.delete("/labels/{label_id}")
async def delete_label(label_id: int, v: Viewer = Depends(senior), session: AsyncSession = Depends(get_session)):
    label = await session.get(Label, label_id)
    if label is None:
        raise not_found("Метка не найдена")
    for task in await session.scalars(select(Task).where(Task.label_ids.any(label_id))):
        task.label_ids = [x for x in task.label_ids if x != label_id]
    await session.delete(label)
    await session.commit()
    return {"ok": True}
