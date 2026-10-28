// Редактор напоминаний задачи: «за N до срока», «в момент», «каждые N», «после просрочки».
import { Plus, Trash2 } from 'lucide-react'
import type { Reminder, ReminderKind } from '../api'
import { Field } from '../ui'
import { fmtDate, fromInput, toInput } from '../util'

const KINDS: { value: ReminderKind; label: string; hint: string }[] = [
	{ value: 'before', label: 'До срока', hint: 'Один раз, за указанное время до дедлайна' },
	{ value: 'at', label: 'В момент', hint: 'Один раз, в выбранные дату и время' },
	{ value: 'repeat', label: 'Повторять', hint: 'Каждые N, пока задача не выполнена' },
	{ value: 'overdue', label: 'Просрочка', hint: 'Когда срок прошёл, и дальше каждые N (0 — один раз)' },
]

const UNITS = [
	{ value: 1, label: 'мин' },
	{ value: 60, label: 'ч' },
	{ value: 1440, label: 'дн' },
]

function MinutesInput({ value, onChange }: { value: number | null | undefined; onChange: (v: number) => void }) {
	const minutes = value ?? 0
	const unit = minutes && minutes % 1440 === 0 ? 1440 : minutes && minutes % 60 === 0 ? 60 : 1
	return (
		<div className='row gap'>
			<input type='number' min={0} className='input narrow' value={minutes / unit} onChange={(e) => onChange(Math.max(0, Number(e.target.value)) * unit)} />
			<select className='input narrow' value={unit} onChange={(e) => onChange((minutes / unit) * Number(e.target.value))}>
				{UNITS.map((u) => (
					<option key={u.value} value={u.value}>
						{u.label}
					</option>
				))}
			</select>
		</div>
	)
}

export function newReminder(kind: ReminderKind = 'before'): Reminder {
	if (kind === 'before') return { kind, offset_minutes: 60 }
	if (kind === 'repeat') return { kind, interval_minutes: 240 }
	if (kind === 'overdue') return { kind, interval_minutes: 180 }
	return { kind, at: null }
}

export default function ReminderEditor({ items, onChange, allowAt = true, hasDeadline = true }: { items: Reminder[]; onChange: (items: Reminder[]) => void; allowAt?: boolean; hasDeadline?: boolean }) {
	const set = (i: number, patch: Partial<Reminder>) => onChange(items.map((r, j) => (j === i ? { ...r, ...patch } : r)))
	const kinds = KINDS.filter((k) => allowAt || k.value !== 'at')
	return (
		<div className='reminders'>
			{items.length === 0 && <div className='muted small'>Напоминаний нет</div>}
			{items.map((r, i) => (
				<div key={i} className='reminder-row'>
					<div className='row gap wrap'>
						<select className='input' value={r.kind} onChange={(e) => onChange(items.map((x, j) => (j === i ? newReminder(e.target.value as ReminderKind) : x)))}>
							{kinds.map((k) => (
								<option key={k.value} value={k.value}>
									{k.label}
								</option>
							))}
						</select>
						{r.kind === 'before' && (
							<>
								<span className='muted small'>за</span>
								<MinutesInput value={r.offset_minutes} onChange={(v) => set(i, { offset_minutes: v })} />
							</>
						)}
						{(r.kind === 'repeat' || r.kind === 'overdue') && (
							<>
								<span className='muted small'>каждые</span>
								<MinutesInput value={r.interval_minutes} onChange={(v) => set(i, { interval_minutes: v })} />
							</>
						)}
						{(r.kind === 'at' || r.kind === 'repeat') && (
							<input
								type='datetime-local'
								className='input'
								value={toInput(r.at)}
								onChange={(e) => set(i, { at: fromInput(e.target.value) })}
								title={r.kind === 'repeat' ? 'Начать с (пусто — сразу)' : 'Когда напомнить'}
							/>
						)}
						<button type='button' className='icon-btn danger' onClick={() => onChange(items.filter((_, j) => j !== i))} aria-label='Удалить'>
							<Trash2 size={16} />
						</button>
					</div>
					<input className='input' placeholder='Своя приписка (необязательно)' value={r.text ?? ''} onChange={(e) => set(i, { text: e.target.value })} maxLength={512} />
					<div className='muted tiny'>
						{kinds.find((k) => k.value === r.kind)?.hint}
						{(r.kind === 'before' || r.kind === 'overdue') && !hasDeadline && ' · нужен дедлайн задачи'}
						{r.next_at && r.active && ` · следующее: ${fmtDate(r.next_at)}`}
					</div>
				</div>
			))}
			<Field label=''>
				<button type='button' className='btn ghost small' onClick={() => onChange([...items, newReminder(hasDeadline ? 'before' : 'repeat')])}>
					<Plus size={14} /> Добавить напоминание
				</button>
			</Field>
		</div>
	)
}
