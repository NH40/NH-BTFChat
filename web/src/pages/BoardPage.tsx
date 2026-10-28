// Канбан: колонки листаются вбок, карточки перетаскиваются долгим нажатием (между колонками и внутри).
import {
	closestCorners,
	DndContext,
	DragOverlay,
	MouseSensor,
	TouchSensor,
	useDroppable,
	useSensor,
	useSensors,
	type DragEndEvent,
	type DragOverEvent,
	type DragStartEvent,
} from '@dnd-kit/core'
import { arrayMove, SortableContext, useSortable, verticalListSortingStrategy } from '@dnd-kit/sortable'
import { CSS } from '@dnd-kit/utilities'
import { ChevronDown, Eye, EyeOff, Plus, Search, Settings2, User as UserIcon } from 'lucide-react'
import { useCallback, useEffect, useMemo, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { api, type Board, type Column, type Label, type TaskCard } from '../api'
import BoardSettingsSheet from '../components/BoardSettingsSheet'
import TaskCardView from '../components/TaskCardView'
import TaskCreateSheet from '../components/TaskCreateSheet'
import { useStore } from '../store'
import { haptic } from '../tg'
import { Sheet, Spinner } from '../ui'

const BOARD_KEY = 'btf.board'

function readBoard(): number | null {
	try {
		return Number(localStorage.getItem(BOARD_KEY)) || null
	} catch {
		return null
	}
}

function SortableCard({ task, labels, onOpen }: { task: TaskCard; labels: Label[]; onOpen: () => void }) {
	const { attributes, listeners, setNodeRef, transform, transition, isDragging } = useSortable({ id: task.id })
	return (
		<div ref={setNodeRef} style={{ transform: CSS.Transform.toString(transform), transition, opacity: isDragging ? 0.35 : 1 }} {...attributes} {...listeners}>
			<TaskCardView task={task} labels={labels} onClick={onOpen} />
		</div>
	)
}

function ColumnView({ column, tasks, labels, onOpen, onAdd }: { column: Column; tasks: TaskCard[]; labels: Label[]; onOpen: (id: number) => void; onAdd: () => void }) {
	const { setNodeRef, isOver } = useDroppable({ id: `col-${column.id}` })
	const open = tasks.filter((t) => !t.completed_at).length
	const overLimit = column.wip_limit != null && open > column.wip_limit
	return (
		<div className={`column ${isOver ? 'over' : ''}`}>
			<div className='column-head'>
				<span className='column-name'>{column.name}</span>
				<span className={`count ${overLimit ? 'danger' : ''}`}>
					{tasks.length}
					{column.wip_limit != null && `/${column.wip_limit}`}
				</span>
				<button className='icon-btn small' onClick={onAdd} aria-label='Добавить задачу'>
					<Plus size={15} />
				</button>
			</div>
			<SortableContext id={`col-${column.id}`} items={tasks.map((t) => t.id)} strategy={verticalListSortingStrategy}>
				<div ref={setNodeRef} className='column-body'>
					{tasks.map((t) => (
						<SortableCard key={t.id} task={t} labels={labels} onOpen={() => onOpen(t.id)} />
					))}
					{tasks.length === 0 && <div className='column-empty'>Перетащите сюда</div>}
				</div>
			</SortableContext>
		</div>
	)
}

type Grouped = Record<number, TaskCard[]>

function group(board: Board, tasks: TaskCard[]): Grouped {
	const out: Grouped = {}
	for (const c of board.columns) out[c.id] = []
	for (const t of [...tasks].sort((a, b) => a.position - b.position)) (out[t.column_id] ??= []).push(t)
	return out
}

export default function BoardPage() {
	const { boards, me, run, reloadBoards, reloadMe } = useStore()
	const navigate = useNavigate()
	const [boardId, setBoardId] = useState<number | null>(readBoard)
	const board = boards.find((b) => b.id === boardId) ?? boards[0]
	const [grouped, setGrouped] = useState<Grouped>({})
	const [loading, setLoading] = useState(true)
	const [mine, setMine] = useState(false)
	const [showDone, setShowDone] = useState(false)
	const [query, setQuery] = useState('')
	const [searchOpen, setSearchOpen] = useState(false)
	const [picker, setPicker] = useState(false)
	const [settings, setSettings] = useState(false)
	const [creating, setCreating] = useState<{ column?: number } | null>(null)
	const [active, setActive] = useState<TaskCard | null>(null)

	const load = useCallback(async () => {
		if (!board) return
		const params = new URLSearchParams()
		if (showDone) params.set('show_done', 'true')
		if (mine && me) params.set('assignee', String(me.id))
		if (query.trim()) params.set('q', query.trim())
		const tasks = await api.get<TaskCard[]>(`/boards/${board.id}/tasks?${params}`)
		setGrouped(group(board, tasks))
		setLoading(false)
	}, [board, showDone, mine, me, query])

	useEffect(() => {
		const id = setTimeout(() => load().catch(() => setLoading(false)), query ? 300 : 0)
		return () => clearTimeout(id)
	}, [load, query])

	const selectBoard = (id: number) => {
		setBoardId(id)
		try {
			localStorage.setItem(BOARD_KEY, String(id))
		} catch {
			/* приватный режим */
		}
		setPicker(false)
		setLoading(true)
	}

	const sensors = useSensors(
		useSensor(MouseSensor, { activationConstraint: { distance: 6 } }),
		useSensor(TouchSensor, { activationConstraint: { delay: 220, tolerance: 8 } }),
	)

	const findColumn = useCallback(
		(id: string | number): number | null => {
			if (typeof id === 'string' && id.startsWith('col-')) return Number(id.slice(4))
			for (const [col, list] of Object.entries(grouped)) if (list.some((t) => t.id === id)) return Number(col)
			return null
		},
		[grouped],
	)

	const onDragStart = (e: DragStartEvent) => {
		haptic()
		const col = findColumn(e.active.id)
		setActive(col != null ? (grouped[col].find((t) => t.id === e.active.id) ?? null) : null)
	}

	const onDragOver = (e: DragOverEvent) => {
		if (!e.over) return
		const from = findColumn(e.active.id)
		const to = findColumn(e.over.id)
		if (from == null || to == null || from === to) return
		setGrouped((g) => {
			const item = g[from].find((t) => t.id === e.active.id)
			if (!item) return g
			const target = g[to]
			const overIndex = target.findIndex((t) => t.id === e.over!.id)
			const index = overIndex >= 0 ? overIndex : target.length
			return { ...g, [from]: g[from].filter((t) => t.id !== item.id), [to]: [...target.slice(0, index), { ...item, column_id: to }, ...target.slice(index)] }
		})
	}

	const onDragEnd = async (e: DragEndEvent) => {
		setActive(null)
		const col = findColumn(e.active.id)
		if (col == null || !e.over) return
		let list = grouped[col]
		const oldIndex = list.findIndex((t) => t.id === e.active.id)
		const overIndex = list.findIndex((t) => t.id === e.over!.id)
		if (overIndex >= 0 && overIndex !== oldIndex) list = arrayMove(list, oldIndex, overIndex)
		const index = list.findIndex((t) => t.id === e.active.id)
		const prev = list[index - 1]?.position
		const next = list[index + 1]?.position
		const position = prev != null && next != null ? (prev + next) / 2 : prev != null ? prev + 1 : next != null ? next - 1 : 1
		setGrouped((g) => ({ ...g, [col]: list.map((t) => (t.id === e.active.id ? { ...t, position } : t)) }))
		const res = await run(() => api.post<{ status: string | null }>(`/tasks/${e.active.id}/move`, { column_id: col, position }))
		if (res?.status === 'completed') haptic('success')
		await Promise.all([load(), reloadBoards(), reloadMe()])
	}

	const totals = useMemo(() => Object.values(grouped).reduce((n, l) => n + l.length, 0), [grouped])

	if (!board) return <Spinner />

	return (
		<div className='board-page'>
			<header className='page-head'>
				<button className='board-switch' onClick={() => setPicker(true)}>
					<span className='board-color' style={{ background: board.color }} />
					<span className='board-name'>{board.name}</span>
					<ChevronDown size={16} />
				</button>
				<span className='spacer' />
				<button className={`icon-btn ${searchOpen ? 'on' : ''}`} onClick={() => setSearchOpen(!searchOpen)} aria-label='Поиск'>
					<Search size={18} />
				</button>
				<button className={`icon-btn ${mine ? 'on' : ''}`} onClick={() => setMine(!mine)} aria-label='Только мои' title='Только мои'>
					<UserIcon size={18} />
				</button>
				<button className={`icon-btn ${showDone ? 'on' : ''}`} onClick={() => setShowDone(!showDone)} aria-label='Показывать все выполненные' title='Все выполненные'>
					{showDone ? <Eye size={18} /> : <EyeOff size={18} />}
				</button>
				{me?.is_senior && (
					<button className='icon-btn' onClick={() => setSettings(true)} aria-label='Настройки доски'>
						<Settings2 size={18} />
					</button>
				)}
			</header>
			{searchOpen && <input className='input search' autoFocus placeholder='Поиск по названию' value={query} onChange={(e) => setQuery(e.target.value)} />}
			{loading ? (
				<Spinner />
			) : (
				<DndContext sensors={sensors} collisionDetection={closestCorners} onDragStart={onDragStart} onDragOver={onDragOver} onDragEnd={onDragEnd} onDragCancel={() => setActive(null)}>
					<div className='columns'>
						{board.columns.map((c) => (
							<ColumnView key={c.id} column={c} tasks={grouped[c.id] ?? []} labels={board.labels} onOpen={(id) => navigate(`/task/${id}`)} onAdd={() => setCreating({ column: c.id })} />
						))}
					</div>
					<DragOverlay>{active && <TaskCardView task={active} labels={board.labels} dragging />}</DragOverlay>
				</DndContext>
			)}
			{!loading && totals === 0 && !query && <div className='muted center small'>Пока пусто — создайте первую задачу кнопкой «+»</div>}
			<button className='fab' onClick={() => setCreating({})} aria-label='Новая задача'>
				<Plus size={24} />
			</button>

			{picker && (
				<Sheet title='Доски' onClose={() => setPicker(false)}>
					<div className='stack'>
						{boards.map((b) => (
							<button key={b.id} className={`list-btn ${b.id === board.id ? 'on' : ''}`} onClick={() => selectBoard(b.id)}>
								<span className='board-color' style={{ background: b.color }} />
								<span className='grow'>{b.name}</span>
								<span className='muted small'>{b.open_count} открыто</span>
							</button>
						))}
						{me?.is_senior && <NewBoard onCreated={selectBoard} />}
					</div>
				</Sheet>
			)}
			{settings && <BoardSettingsSheet board={board} onClose={() => setSettings(false)} onDeleted={() => (setSettings(false), selectBoard(boards.find((b) => b.id !== board.id)?.id ?? 0))} />}
			{creating && (
				<TaskCreateSheet
					board={board}
					columnId={creating.column}
					onClose={() => setCreating(null)}
					onCreated={async () => {
						setCreating(null)
						await Promise.all([load(), reloadBoards(), reloadMe()])
					}}
				/>
			)}
		</div>
	)
}

function NewBoard({ onCreated }: { onCreated: (id: number) => void }) {
	const { run, reloadBoards } = useStore()
	const [name, setName] = useState('')
	return (
		<div className='row gap'>
			<input className='input' placeholder='Новая доска' value={name} onChange={(e) => setName(e.target.value)} maxLength={128} />
			<button
				className='btn primary'
				disabled={!name.trim()}
				onClick={async () => {
					const res = await run(() => api.post<{ id: number }>('/boards', { name: name.trim() }), 'Доска создана')
					if (res) {
						await reloadBoards()
						onCreated(res.id)
					}
				}}
			>
				<Plus size={16} />
			</button>
		</div>
	)
}
