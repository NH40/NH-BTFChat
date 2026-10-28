// Редактор повтора: интервал / дни недели / число месяца, режим, срок копии, ротация исполнителей.
import type { SeriesRule, StaffMember } from '../api'
import { Field, PeoplePicker, Segmented, Toggle } from '../ui'
import { fromInput, toInput } from '../util'

export interface SeriesValue {
	rule: SeriesRule
	mode: 'schedule' | 'after_done'
	deadline_minutes: number | null
	rotate: boolean
	rotation: number[]
	ends_at: string | null
}

export function defaultSeries(): SeriesValue {
	return { rule: { type: 'weekly', weekdays: [0], time: '10:00' }, mode: 'schedule', deadline_minutes: 1440, rotate: false, rotation: [], ends_at: null }
}

const WEEKDAYS = ['Пн', 'Вт', 'Ср', 'Чт', 'Пт', 'Сб', 'Вс']

export default function SeriesEditor({ value, onChange, staff }: { value: SeriesValue; onChange: (v: SeriesValue) => void; staff: StaffMember[] }) {
	const rule = value.rule
	const setRule = (patch: Partial<SeriesRule>) => onChange({ ...value, rule: { ...rule, ...patch } })
	const deadlineHours = value.deadline_minutes ? value.deadline_minutes / 60 : 0
	return (
		<div className='stack'>
			<Segmented
				value={rule.type}
				options={[
					{ value: 'weekly', label: 'По дням недели' },
					{ value: 'interval', label: 'Каждые N' },
					{ value: 'monthly', label: 'По числам' },
				]}
				onChange={(type) =>
					onChange({
						...value,
						rule:
							type === 'weekly'
								? { type, weekdays: [0], time: '10:00' }
								: type === 'monthly'
									? { type, day: 1, time: '10:00' }
									: { type, n: 1, unit: 'days', start: undefined },
					})
				}
			/>
			{rule.type === 'weekly' && (
				<div className='weekdays'>
					{WEEKDAYS.map((d, i) => {
						const on = rule.weekdays?.includes(i)
						return (
							<button
								key={d}
								type='button'
								className={`weekday ${on ? 'on' : ''}`}
								onClick={() => setRule({ weekdays: on ? rule.weekdays!.filter((x) => x !== i) : [...(rule.weekdays ?? []), i].sort() })}
							>
								{d}
							</button>
						)
					})}
				</div>
			)}
			{rule.type === 'monthly' && (
				<Field label='Число месяца' hint='В коротком месяце — последний день'>
					<input type='number' min={1} max={31} className='input narrow' value={rule.day ?? 1} onChange={(e) => setRule({ day: Number(e.target.value) })} />
				</Field>
			)}
			{rule.type === 'interval' && (
				<div className='row gap wrap'>
					<span className='muted small'>каждые</span>
					<input type='number' min={1} className='input narrow' value={rule.n ?? 1} onChange={(e) => setRule({ n: Math.max(1, Number(e.target.value)) })} />
					<select className='input narrow' value={rule.unit} onChange={(e) => setRule({ unit: e.target.value as 'hours' | 'days' })}>
						<option value='hours'>часов</option>
						<option value='days'>дней</option>
					</select>
					<span className='muted small'>с</span>
					<input type='datetime-local' className='input' value={toInput(rule.start)} onChange={(e) => setRule({ start: fromInput(e.target.value) ?? undefined })} />
				</div>
			)}
			{rule.type !== 'interval' && (
				<Field label='Время'>
					<input type='time' className='input narrow' value={rule.time ?? '10:00'} onChange={(e) => setRule({ time: e.target.value })} />
				</Field>
			)}
			<Field label='Когда создавать новую копию'>
				<Segmented
					value={value.mode}
					options={[
						{ value: 'schedule', label: 'Строго по расписанию' },
						{ value: 'after_done', label: 'После выполнения' },
					]}
					onChange={(mode) => onChange({ ...value, mode })}
				/>
			</Field>
			<Field label='Срок у каждой копии' hint='Через сколько часов после появления — дедлайн (0 — без срока)'>
				<input
					type='number'
					min={0}
					className='input narrow'
					value={deadlineHours}
					onChange={(e) => onChange({ ...value, deadline_minutes: Number(e.target.value) > 0 ? Math.round(Number(e.target.value) * 60) : null })}
				/>
			</Field>
			<Toggle checked={value.rotate} onChange={(rotate) => onChange({ ...value, rotate })} label='Исполнитель по очереди' />
			{value.rotate && (
				<Field label='Очередь' hint='Каждая новая копия — следующему по списку'>
					<PeoplePicker staff={staff} value={value.rotation} onChange={(rotation) => onChange({ ...value, rotation })} />
				</Field>
			)}
			<Field label='Закончить повтор' hint='Пусто — бессрочно'>
				<input type='datetime-local' className='input' value={toInput(value.ends_at)} onChange={(e) => onChange({ ...value, ends_at: fromInput(e.target.value) })} />
			</Field>
		</div>
	)
}
