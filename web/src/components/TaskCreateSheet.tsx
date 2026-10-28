// Создание задачи: всё основное сразу, напоминания — по умолчанию или свои, повтор — опционально.
import { useState } from 'react'
import { api, type Board, type Reminder } from '../api'
import { useStore } from '../store'
import { Field, PeoplePicker, Segmented, Sheet, Toggle } from '../ui'
import { fromInput, PRIORITIES } from '../util'
import ReminderEditor from './ReminderEditor'
import SeriesEditor, { defaultSeries, type SeriesValue } from './SeriesEditor'

export default function TaskCreateSheet({ board, columnId, onClose, onCreated }: { board: Board; columnId?: number; onClose: () => void; onCreated: (id: number) => void }) {
	const { staff, me, run } = useStore()
	const [title, setTitle] = useState('')
	const [description, setDescription] = useState('')
	const [column, setColumn] = useState<number>(columnId ?? board.columns.find((c) => !c.is_done)?.id ?? board.columns[0]?.id)
	const [assignees, setAssignees] = useState<number[]>(me ? [me.id] : [])
	const [deadline, setDeadline] = useState('')
	const [hard, setHard] = useState(true)
	const [priority, setPriority] = useState(1)
	const [labels, setLabels] = useState<number[]>([])
	const [checklist, setChecklist] = useState('')
	const [customRem, setCustomRem] = useState(false)
	const [rems, setRems] = useState<Reminder[]>([])
	const [repeat, setRepeat] = useState(false)
	const [series, setSeries] = useState<SeriesValue>(defaultSeries())
	const [notify, setNotify] = useState(true)
	const [busy, setBusy] = useState(false)

	const submit = async () => {
		if (!title.trim()) return
		setBusy(true)
		const res = await run(async () => {
			const created = await api.post<{ id: number }>('/tasks', {
				board_id: board.id,
				column_id: column,
				title: title.trim(),
				description: description.trim() || null,
				assignees,
				deadline: fromInput(deadline),
				deadline_hard: hard,
				priority,
				label_ids: labels,
				checklist: checklist.split('\n').map((s) => s.trim()).filter(Boolean),
				reminders: customRem ? rems : null,
				notify,
			})
			if (repeat) await api.put(`/tasks/${created.id}/series`, series)
			return created
		}, 'Задача создана')
		setBusy(false)
		if (res) onCreated(res.id)
	}

	return (
		<Sheet
			title='Новая задача'
			onClose={onClose}
			footer={
				<button className='btn primary block' disabled={!title.trim() || busy} onClick={submit}>
					Создать
				</button>
			}
		>
			<div className='stack'>
				<input className='input big' autoFocus placeholder='Что нужно сделать?' value={title} onChange={(e) => setTitle(e.target.value)} maxLength={256} />
				<textarea className='input' rows={3} placeholder='Описание, ссылки, детали' value={description} onChange={(e) => setDescription(e.target.value)} />
				<Field label='Исполнители'>
					<PeoplePicker staff={staff} value={assignees} onChange={setAssignees} />
				</Field>
				<div className='grid2'>
					<Field label='Дедлайн'>
						<input type='datetime-local' className='input' value={deadline} onChange={(e) => setDeadline(e.target.value)} />
					</Field>
					<Field label='Колонка'>
						<select className='input' value={column} onChange={(e) => setColumn(Number(e.target.value))}>
							{board.columns.map((c) => (
								<option key={c.id} value={c.id}>
									{c.name}
								</option>
							))}
						</select>
					</Field>
				</div>
				{deadline && <Toggle checked={hard} onChange={setHard} label={hard ? 'Жёсткий срок' : 'Мягкий срок (ориентир)'} />}
				<Field label='Приоритет'>
					<Segmented value={priority} options={PRIORITIES.map((p) => ({ value: p.value, label: p.label }))} onChange={setPriority} />
				</Field>
				{board.labels.length > 0 && (
					<Field label='Метки'>
						<div className='row gap wrap'>
							{board.labels.map((l) => (
								<button
									key={l.id}
									type='button'
									className={`label-toggle ${labels.includes(l.id) ? 'on' : ''}`}
									style={{ borderColor: l.color, background: labels.includes(l.id) ? l.color : 'transparent' }}
									onClick={() => setLabels(labels.includes(l.id) ? labels.filter((x) => x !== l.id) : [...labels, l.id])}
								>
									{l.name}
								</button>
							))}
						</div>
					</Field>
				)}
				<Field label='Подзадачи' hint='Каждая строка — отдельный пункт'>
					<textarea className='input' rows={3} value={checklist} onChange={(e) => setChecklist(e.target.value)} placeholder={'Подготовить текст\nСогласовать\nОпубликовать'} />
				</Field>
				<Toggle checked={customRem} onChange={setCustomRem} label='Свои напоминания (иначе — по умолчанию из настроек)' />
				{customRem && <ReminderEditor items={rems} onChange={setRems} hasDeadline={Boolean(deadline)} />}
				<Toggle checked={repeat} onChange={setRepeat} label='Повторяющаяся задача' />
				{repeat && <SeriesEditor value={series} onChange={setSeries} staff={staff} />}
				<Toggle checked={notify} onChange={setNotify} label='Объявить в чате админов с упоминанием' />
			</div>
		</Sheet>
	)
}
