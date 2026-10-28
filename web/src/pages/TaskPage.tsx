// Карточка задачи: поля, исполнители, подзадачи, напоминания, повтор, время, комментарии, история.
import { Archive, Bell, CheckCircle2, Hand, Pause, Play, Plus, Repeat, Send, Trash2, Users } from 'lucide-react'
import { useEffect, useState } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import { api, type Reminder, type TaskDetail } from '../api'
import ReminderEditor from '../components/ReminderEditor'
import SeriesEditor, { defaultSeries, type SeriesValue } from '../components/SeriesEditor'
import { deadlineTone } from '../components/TaskCardView'
import { useLoad, useStore } from '../store'
import { confirmAction } from '../tg'
import { Avatar, Empty, Field, PeoplePicker, Section, Sheet, Spinner, Toggle } from '../ui'
import { duration, fmtDate, fromInput, PRIORITIES, relative, toInput } from '../util'

const ACTIONS: Record<string, string> = {
	created: 'создал задачу',
	changed: 'изменил',
	moved: 'перенёс',
	completed: 'выполнил',
	reopened: 'переоткрыл',
	taken: 'взял в работу',
	assignees: 'сменил исполнителей',
	subtask_added: 'добавил подзадачу',
	subtask_done: 'отметил подзадачу',
	subtask_undone: 'снял отметку',
	subtask_removed: 'удалил подзадачу',
	time: 'записал время',
	reminders: 'настроил напоминания',
	reminded: 'напоминание отправлено',
	series: 'настроил повтор',
	series_off: 'выключил повтор',
	spawned: 'создана по расписанию',
	pinged: 'пингнул исполнителей',
	archived: 'отправил в архив',
	unarchived: 'вернул из архива',
}
const FIELDS: Record<string, string> = {
	title: 'название',
	description: 'описание',
	priority: 'приоритет',
	label_ids: 'метки',
	deadline: 'дедлайн',
	deadline_hard: 'тип срока',
	start_at: 'начало',
	estimate_minutes: 'оценку',
}

function historyText(h: TaskDetail['history'][number]): string {
	const d = h.data as Record<string, unknown>
	let text = ACTIONS[h.action] ?? h.action
	if (h.action === 'changed') text += ` ${FIELDS[String(d.field)] ?? d.field}`
	if (h.action === 'moved') text += ` в «${d.to}»`
	if (h.action === 'completed' && d.on_time === false) text += ' (с опозданием)'
	if (h.action === 'time' && typeof d.seconds === 'number') text += ` ${duration(d.seconds)}`
	if (typeof d.text === 'string') text += `: ${d.text}`
	if (typeof d.rule === 'string') text += `: ${d.rule}`
	return text
}

export default function TaskPage() {
	const { id } = useParams()
	const navigate = useNavigate()
	const { boards, staff, me, run, reloadMe, reloadBoards } = useStore()
	const { data: task, reload, loading } = useLoad(() => api.get<TaskDetail>(`/tasks/${id}`), [id])
	const [title, setTitle] = useState('')
	const [description, setDescription] = useState('')
	const [rems, setRems] = useState<Reminder[] | null>(null)
	const [assignSheet, setAssignSheet] = useState(false)
	const [seriesSheet, setSeriesSheet] = useState<SeriesValue | null>(null)
	const [newItem, setNewItem] = useState('')
	const [comment, setComment] = useState('')
	const [manual, setManual] = useState('')
	const [showHistory, setShowHistory] = useState(false)

	useEffect(() => {
		if (!task) return
		setTitle(task.title)
		setDescription(task.description ?? '')
		setRems(null)
	}, [task])

	if (loading && !task) return <Spinner />
	if (!task) return <Empty title='Задача не найдена' />

	const board = boards.find((b) => b.id === task.board_id)
	const edit = task.can_edit
	const act = async (fn: () => Promise<unknown>, ok?: string) => {
		const res = await run(fn, ok)
		await Promise.all([reload(), reloadMe(), reloadBoards()])
		return res
	}
	const patch = (body: Record<string, unknown>) => act(() => api.patch(`/tasks/${task.id}`, body))
	const amAssignee = task.assignees.some((a) => a.id === me?.id)
	const myTimer = me?.timer?.task_id === task.id

	return (
		<div className='task-page'>
			<div className='task-head'>
				<div className='row gap wrap small muted'>
					{board && (
						<span className='row gap-s'>
							<span className='board-color' style={{ background: board.color }} />
							{board.name}
						</span>
					)}
					<span>#{task.id}</span>
					{task.series && (
						<span className='row gap-s'>
							<Repeat size={12} /> {task.series.describe}
						</span>
					)}
				</div>
				{edit ? (
					<textarea className='title-edit' rows={1} value={title} onChange={(e) => setTitle(e.target.value)} onBlur={() => title.trim() && title !== task.title && patch({ title })} />
				) : (
					<h2>{task.title}</h2>
				)}
				{task.completed_at && (
					<div className='banner ok'>
						<CheckCircle2 size={16} /> Выполнена {fmtDate(task.completed_at)}
						{task.completed_by && ` · ${task.completed_by.name}`}
					</div>
				)}
				{task.overdue && <div className='banner danger'>Просрочена на {relative(task.deadline).replace(' назад', '')}</div>}
			</div>

			<div className='action-row'>
				{!task.completed_at && !amAssignee && (
					<button className='btn' onClick={() => act(() => api.post(`/tasks/${task.id}/take`), 'Взято в работу')}>
						<Hand size={16} /> Взять
					</button>
				)}
				{!task.completed_at && edit && (
					<button className='btn primary' onClick={() => act(() => api.post(`/tasks/${task.id}/complete`), 'Выполнено')}>
						<CheckCircle2 size={16} /> Готово
					</button>
				)}
				{!task.completed_at &&
					(myTimer ? (
						<button className='btn live' onClick={() => act(() => api.post('/timer/stop'), 'Время записано')}>
							<Pause size={16} /> Стоп
						</button>
					) : (
						<button className='btn' onClick={() => act(() => api.post(`/tasks/${task.id}/timer/start`), 'Таймер запущен')}>
							<Play size={16} /> Таймер
						</button>
					))}
				{!task.completed_at && task.assignees.length > 0 && (
					<button className='btn ghost' onClick={() => act(() => api.post(`/tasks/${task.id}/ping`), 'Напомнил в чате админов')}>
						<Bell size={16} /> Пинг
					</button>
				)}
			</div>

			<div className='info-grid'>
				<Field label='Колонка'>
					<select className='input' disabled={!edit} value={task.column_id} onChange={(e) => act(() => api.post(`/tasks/${task.id}/move`, { column_id: Number(e.target.value) }))}>
						{board?.columns.map((c) => (
							<option key={c.id} value={c.id}>
								{c.name}
							</option>
						))}
					</select>
				</Field>
				<Field label='Приоритет'>
					<select className='input' disabled={!edit} value={task.priority} onChange={(e) => patch({ priority: Number(e.target.value) })} style={{ color: PRIORITIES[task.priority]?.color }}>
						{PRIORITIES.map((p) => (
							<option key={p.value} value={p.value}>
								{p.label}
							</option>
						))}
					</select>
				</Field>
				<Field label={`Дедлайн${task.deadline ? ` · ${relative(task.deadline)}` : ''}`}>
					<input
						type='datetime-local'
						className={`input ${deadlineTone(task)}`}
						disabled={!edit}
						defaultValue={toInput(task.deadline)}
						key={task.deadline ?? 'none'}
						onBlur={(e) => fromInput(e.target.value) !== (task.deadline ? fromInput(toInput(task.deadline)) : null) && patch({ deadline: fromInput(e.target.value) })}
					/>
				</Field>
				<Field label='Оценка, ч'>
					<input
						type='number'
						min={0}
						step={0.5}
						className='input'
						disabled={!edit}
						defaultValue={task.estimate_minutes ? task.estimate_minutes / 60 : ''}
						onBlur={(e) => patch({ estimate_minutes: Number(e.target.value) > 0 ? Math.round(Number(e.target.value) * 60) : null })}
					/>
				</Field>
			</div>
			{task.deadline && edit && <Toggle checked={task.deadline_hard} onChange={(v) => patch({ deadline_hard: v })} label={task.deadline_hard ? 'Жёсткий срок' : 'Мягкий срок (ориентир)'} />}

			{board && board.labels.length > 0 && (
				<div className='row gap wrap'>
					{board.labels.map((l) => {
						const on = task.label_ids.includes(l.id)
						return (
							<button
								key={l.id}
								disabled={!edit}
								className={`label-toggle ${on ? 'on' : ''}`}
								style={{ borderColor: l.color, background: on ? l.color : 'transparent' }}
								onClick={() => patch({ label_ids: on ? task.label_ids.filter((x) => x !== l.id) : [...task.label_ids, l.id] })}
							>
								{l.name}
							</button>
						)
					})}
				</div>
			)}

			<Section
				title='Исполнители'
				action={
					edit && (
						<button className='icon-btn small' onClick={() => setAssignSheet(true)} aria-label='Изменить исполнителей'>
							<Users size={15} />
						</button>
					)
				}
			>
				{task.assignees.length === 0 ? (
					<div className='muted small'>Не назначены</div>
				) : (
					<div className='row gap wrap'>
						{task.assignees.map((a) => (
							<span key={a.id} className='person-chip on static'>
								<Avatar user={a} size={20} />
								{a.name}
							</span>
						))}
					</div>
				)}
			</Section>

			<Section title='Описание'>
				<textarea
					className='input'
					rows={Math.min(10, Math.max(3, description.split('\n').length))}
					disabled={!edit}
					placeholder={edit ? 'Детали, ссылки, договорённости' : 'Нет описания'}
					value={description}
					onChange={(e) => setDescription(e.target.value)}
					onBlur={() => description !== (task.description ?? '') && patch({ description: description || null })}
				/>
			</Section>

			<Section title={`Подзадачи ${task.checklist.total ? `${task.checklist.done}/${task.checklist.total}` : ''}`}>
				{task.checklist.total > 0 && (
					<div className='progress'>
						<span style={{ width: `${(100 * task.checklist.done) / task.checklist.total}%` }} />
					</div>
				)}
				{task.checklist_items.map((c) => (
					<div key={c.id} className={`check-row ${c.done ? 'done' : ''}`}>
						<input type='checkbox' checked={c.done} onChange={(e) => act(() => api.patch(`/checklist/${c.id}`, { done: e.target.checked }))} />
						<span className='grow'>{c.text}</span>
						{c.assignee && <Avatar user={c.assignee} size={20} />}
						{edit && (
							<button className='icon-btn small danger' onClick={() => act(() => api.del(`/checklist/${c.id}`))} aria-label='Удалить подзадачу'>
								<Trash2 size={14} />
							</button>
						)}
					</div>
				))}
				{edit && (
					<form
						className='row gap'
						onSubmit={(e) => {
							e.preventDefault()
							if (newItem.trim()) act(() => api.post(`/tasks/${task.id}/checklist`, { text: newItem.trim() })).then(() => setNewItem(''))
						}}
					>
						<input className='input' placeholder='Новая подзадача' value={newItem} onChange={(e) => setNewItem(e.target.value)} maxLength={512} />
						<button className='btn' disabled={!newItem.trim()}>
							<Plus size={15} />
						</button>
					</form>
				)}
			</Section>

			<Section
				title='Напоминания'
				action={
					edit &&
					rems === null && (
						<button className='btn ghost small' onClick={() => setRems(task.reminders.map(({ kind, offset_minutes, at, interval_minutes, text }) => ({ kind, offset_minutes, at, interval_minutes, text })))}>
							Изменить
						</button>
					)
				}
			>
				{rems === null ? (
					task.reminders.length === 0 ? (
						<div className='muted small'>Нет напоминаний</div>
					) : (
						task.reminders.map((r) => (
							<div key={r.id} className={`rem-line ${r.active ? '' : 'off'}`}>
								<Bell size={13} />
								<span className='grow'>
									{r.kind === 'before' && `За ${duration((r.offset_minutes ?? 0) * 60)} до срока`}
									{r.kind === 'at' && `В ${fmtDate(r.at)}`}
									{r.kind === 'repeat' && `Каждые ${duration((r.interval_minutes ?? 0) * 60)}`}
									{r.kind === 'overdue' && (r.interval_minutes ? `После просрочки, каждые ${duration(r.interval_minutes * 60)}` : 'Один раз при просрочке')}
									{r.text && <span className='muted'> · {r.text}</span>}
								</span>
								<span className='muted tiny'>{r.active && r.next_at ? fmtDate(r.next_at) : r.sent_count ? `отправлено ×${r.sent_count}` : 'выкл'}</span>
							</div>
						))
					)
				) : (
					<>
						<ReminderEditor items={rems} onChange={setRems} hasDeadline={Boolean(task.deadline)} />
						<div className='row gap'>
							<button className='btn primary' onClick={() => act(() => api.put(`/tasks/${task.id}/reminders`, { items: rems }), 'Напоминания сохранены')}>
								Сохранить
							</button>
							<button className='btn ghost' onClick={() => setRems(null)}>
								Отмена
							</button>
						</div>
					</>
				)}
			</Section>

			<Section
				title='Повтор'
				action={
					edit && (
						<button
							className='btn ghost small'
							onClick={() =>
								setSeriesSheet(
									task.series
										? { rule: task.series.rule, mode: task.series.mode, deadline_minutes: task.series.deadline_minutes, rotate: task.series.rotate, rotation: task.series.rotation.map((u) => u.id), ends_at: task.series.ends_at }
										: defaultSeries(),
								)
							}
						>
							{task.series ? 'Изменить' : 'Настроить'}
						</button>
					)
				}
			>
				{task.series ? (
					<div className='stack-s small'>
						<div>
							<Repeat size={13} /> {task.series.describe} · {task.series.mode === 'schedule' ? 'по расписанию' : 'после выполнения'}
						</div>
						{task.series.next_run_at && <div className='muted'>Следующая копия: {fmtDate(task.series.next_run_at)}</div>}
						{task.series.rotate && <div className='muted'>Очередь: {task.series.rotation.map((u) => u.name).join(' → ')}</div>}
					</div>
				) : (
					<div className='muted small'>Разовая задача</div>
				)}
			</Section>

			<Section title={`Время · ${duration(task.time_seconds)}${task.estimate_minutes ? ` из ${duration(task.estimate_minutes * 60)}` : ''}`}>
				{task.estimate_minutes ? (
					<div className={`progress ${task.time_seconds > task.estimate_minutes * 60 ? 'over' : ''}`}>
						<span style={{ width: `${Math.min(100, (100 * task.time_seconds) / (task.estimate_minutes * 60))}%` }} />
					</div>
				) : null}
				{task.time_by_user.map((t) => (
					<div key={t.user.id} className='row gap small'>
						<Avatar user={t.user} size={20} />
						<span className='grow'>{t.user.name}</span>
						<span>{duration(t.seconds)}</span>
					</div>
				))}
				<form
					className='row gap'
					onSubmit={(e) => {
						e.preventDefault()
						const minutes = Math.round(Number(manual.replace(',', '.')) * 60)
						if (minutes > 0) act(() => api.post(`/tasks/${task.id}/time`, { minutes }), 'Время добавлено').then(() => setManual(''))
					}}
				>
					<input className='input' inputMode='decimal' placeholder='Добавить вручную, часов (например 1.5)' value={manual} onChange={(e) => setManual(e.target.value)} />
					<button className='btn' disabled={!manual}>
						<Plus size={15} />
					</button>
				</form>
			</Section>

			<Section title={`Комментарии${task.comment_list.length ? ` · ${task.comment_list.length}` : ''}`}>
				{task.comment_list.map((c) => (
					<div key={c.id} className='comment'>
						<Avatar user={c.user} size={26} />
						<div className='grow'>
							<div className='comment-head'>
								<b>{c.user.name}</b>
								<span className='muted tiny'>{fmtDate(c.created_at)}</span>
								{(c.user.id === me?.id || me?.is_senior) && (
									<button className='icon-btn small' onClick={() => act(() => api.del(`/comments/${c.id}`))} aria-label='Удалить комментарий'>
										<Trash2 size={12} />
									</button>
								)}
							</div>
							<div className='comment-text'>{c.text}</div>
						</div>
					</div>
				))}
				<form
					className='row gap'
					onSubmit={(e) => {
						e.preventDefault()
						if (comment.trim()) act(() => api.post(`/tasks/${task.id}/comments`, { text: comment.trim() })).then(() => setComment(''))
					}}
				>
					<input className='input' placeholder='Написать комментарий' value={comment} onChange={(e) => setComment(e.target.value)} maxLength={4000} />
					<button className='btn primary' disabled={!comment.trim()} aria-label='Отправить'>
						<Send size={15} />
					</button>
				</form>
			</Section>

			<Section
				title='История'
				action={
					<button className='btn ghost small' onClick={() => setShowHistory(!showHistory)}>
						{showHistory ? 'Скрыть' : `Показать (${task.history.length})`}
					</button>
				}
			>
				{showHistory &&
					task.history.map((h) => (
						<div key={h.id} className='history-row'>
							<span className='muted tiny'>{fmtDate(h.created_at)}</span>
							<span>
								<b>{h.user?.name ?? 'Система'}</b> {historyText(h)}
							</span>
						</div>
					))}
				{!showHistory && task.created_by && (
					<div className='muted small'>
						Создал {task.created_by.name}, {fmtDate(task.created_at)}
					</div>
				)}
			</Section>

			{edit && (
				<div className='action-row'>
					<button className='btn ghost' onClick={() => act(() => api.post(`/tasks/${task.id}/archive`, { archived: !task.archived }), task.archived ? 'Возвращена' : 'В архиве')}>
						<Archive size={16} /> {task.archived ? 'Из архива' : 'В архив'}
					</button>
					{(me?.is_senior || task.created_by?.id === me?.id) && (
						<button
							className='btn danger'
							onClick={async () => {
								if (!(await confirmAction('Удалить задачу насовсем?'))) return
								if (await run(() => api.del(`/tasks/${task.id}`), 'Задача удалена')) {
									await reloadBoards()
									navigate(-1)
								}
							}}
						>
							<Trash2 size={16} /> Удалить
						</button>
					)}
				</div>
			)}

			{assignSheet && <AssignSheet task={task} onClose={() => setAssignSheet(false)} onSaved={() => (setAssignSheet(false), reload())} />}
			{seriesSheet && (
				<Sheet
					title='Повтор задачи'
					onClose={() => setSeriesSheet(null)}
					footer={
						<div className='row gap'>
							{task.series && (
								<button className='btn danger' onClick={() => act(() => api.del(`/tasks/${task.id}/series`), 'Повтор выключен').then(() => setSeriesSheet(null))}>
									Выключить
								</button>
							)}
							<button className='btn primary grow' onClick={() => act(() => api.put(`/tasks/${task.id}/series`, seriesSheet), 'Повтор сохранён').then(() => setSeriesSheet(null))}>
								Сохранить
							</button>
						</div>
					}
				>
					<SeriesEditor value={seriesSheet} onChange={setSeriesSheet} staff={staff} />
				</Sheet>
			)}
		</div>
	)
}

function AssignSheet({ task, onClose, onSaved }: { task: TaskDetail; onClose: () => void; onSaved: () => void }) {
	const { staff, run } = useStore()
	const [ids, setIds] = useState(task.assignees.map((a) => a.id))
	const [notify, setNotify] = useState(true)
	return (
		<Sheet
			title='Исполнители'
			onClose={onClose}
			footer={
				<button className='btn primary block' onClick={async () => (await run(() => api.put(`/tasks/${task.id}/assignees`, { user_ids: ids, notify }), 'Сохранено')) && onSaved()}>
					Сохранить
				</button>
			}
		>
			<div className='stack'>
				<PeoplePicker staff={staff} value={ids} onChange={setIds} />
				<Toggle checked={notify} onChange={setNotify} label='Упомянуть новых исполнителей в чате админов' />
			</div>
		</Sheet>
	)
}
