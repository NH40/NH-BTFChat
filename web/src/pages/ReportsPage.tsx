// Отчёты: итоги за период, график по дням, таблица по каждому админу.
import { useState } from 'react'
import { api, type Report } from '../api'
import { useLoad, useStore } from '../store'
import { Avatar, Segmented, Spinner } from '../ui'
import { duration, fmtDay } from '../util'

function DaysChart({ days }: { days: Report['days'] }) {
	const [hover, setHover] = useState<number | null>(null)
	const max = Math.max(1, ...days.map((d) => Math.max(d.completed, d.created)))
	const w = 100 / days.length
	const bar = Math.max(1.2, w * 0.32)
	const h = days[hover ?? -1]
	return (
		<div className='chart'>
			<div className='chart-legend'>
				<span>
					<i className='sw done' /> Выполнено
				</span>
				<span>
					<i className='sw created' /> Создано
				</span>
				{h && (
					<span className='chart-tip'>
						{fmtDay(h.date)}: {h.completed} / {h.created}
					</span>
				)}
			</div>
			<svg viewBox='0 0 100 50' preserveAspectRatio='none' className='chart-svg' onMouseLeave={() => setHover(null)}>
				<line x1='0' y1='49.5' x2='100' y2='49.5' className='chart-axis' />
				{days.map((d, i) => {
					const x = i * w + w / 2
					const hc = (d.completed / max) * 46
					const hn = (d.created / max) * 46
					return (
						<g key={d.date} onMouseEnter={() => setHover(i)} onTouchStart={() => setHover(i)}>
							<rect x={i * w} y='0' width={w} height='50' fill='transparent' />
							<rect x={x - bar - 0.2} y={49.5 - hc} width={bar} height={hc} rx='0.6' className='bar done' />
							<rect x={x + 0.2} y={49.5 - hn} width={bar} height={hn} rx='0.6' className='bar created' />
						</g>
					)
				})}
			</svg>
			<div className='chart-x'>
				<span>{fmtDay(days[0]?.date ?? '')}</span>
				<span>{fmtDay(days[days.length - 1]?.date ?? '')}</span>
			</div>
		</div>
	)
}

export default function ReportsPage() {
	const { boards } = useStore()
	const [days, setDays] = useState(7)
	const [board, setBoard] = useState<number>(0)
	const { data, loading } = useLoad(() => api.get<Report>(`/reports?days=${days}${board ? `&board_id=${board}` : ''}`), [days, board])

	return (
		<div className='page'>
			<header className='page-head'>
				<h2>Отчёты</h2>
				<span className='spacer' />
				{boards.length > 1 && (
					<select className='input narrow' value={board} onChange={(e) => setBoard(Number(e.target.value))}>
						<option value={0}>Все доски</option>
						{boards.map((b) => (
							<option key={b.id} value={b.id}>
								{b.name}
							</option>
						))}
					</select>
				)}
			</header>
			<Segmented
				value={days}
				options={[
					{ value: 1, label: 'Сегодня' },
					{ value: 7, label: '7 дней' },
					{ value: 30, label: '30 дней' },
					{ value: 90, label: '90 дней' },
				]}
				onChange={setDays}
			/>
			{loading || !data ? (
				<Spinner />
			) : (
				<>
					<div className='tiles'>
						<div className='tile'>
							<div className='tile-value'>{data.totals.completed}</div>
							<div className='tile-label'>выполнено</div>
						</div>
						<div className='tile'>
							<div className='tile-value'>{data.totals.on_time + data.totals.late ? `${Math.round((100 * data.totals.on_time) / (data.totals.on_time + data.totals.late))}%` : '—'}</div>
							<div className='tile-label'>в срок</div>
						</div>
						<div className='tile'>
							<div className={`tile-value ${data.totals.overdue ? 'danger-text' : ''}`}>{data.totals.overdue}</div>
							<div className='tile-label'>просрочено сейчас</div>
						</div>
						<div className='tile'>
							<div className='tile-value'>{data.totals.open}</div>
							<div className='tile-label'>открыто</div>
						</div>
						<div className='tile wide'>
							<div className='tile-value'>{duration(data.totals.seconds)}</div>
							<div className='tile-label'>затрачено времени</div>
						</div>
					</div>
					{days > 1 && <DaysChart days={data.days} />}
					<h4 className='section-title'>По команде</h4>
					{data.members.length === 0 && <div className='muted small'>Нет данных за период</div>}
					<div className='stack-s'>
						{data.members.map((m) => (
							<div key={m.user.id} className='member-card'>
								<div className='row gap'>
									<Avatar user={m.user} size={30} />
									<b className='grow'>{m.user.name}</b>
									{m.on_time_pct != null && <span className={`pct ${m.on_time_pct >= 80 ? 'ok' : m.on_time_pct >= 50 ? 'warn' : 'danger'}`}>{m.on_time_pct}% в срок</span>}
								</div>
								<div className='member-stats'>
									<span>
										<b>{m.completed}</b> выполнено
									</span>
									{m.late > 0 && (
										<span>
											<b>{m.late}</b> с опозданием
										</span>
									)}
									<span>
										<b>{m.open}</b> открыто
									</span>
									{m.overdue > 0 && (
										<span className='danger-text'>
											<b>{m.overdue}</b> просрочено
										</span>
									)}
									<span>
										<b>{duration(m.seconds)}</b>
									</span>
									{m.avg_hours != null && (
										<span>
											~<b>{m.avg_hours} ч</b> на задачу
										</span>
									)}
								</div>
							</div>
						))}
					</div>
				</>
			)}
		</div>
	)
}
