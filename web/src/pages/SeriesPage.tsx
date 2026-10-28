import { Repeat } from 'lucide-react'
import { useNavigate } from 'react-router-dom'
import { api } from '../api'
import { useLoad } from '../store'
import { Empty, Spinner } from '../ui'
import { fmtDate } from '../util'

interface SeriesRow {
	id: number
	board_id: number
	task_id: number | null
	title: string
	describe: string
	mode: string
	next_run_at: string | null
}

export default function SeriesPage() {
	const navigate = useNavigate()
	const { data, loading } = useLoad(() => api.get<SeriesRow[]>('/series'), [])
	return (
		<div className='page'>
			<header className='page-head'>
				<h2>Повторы</h2>
			</header>
			{loading ? (
				<Spinner />
			) : !data?.length ? (
				<Empty icon={<Repeat size={36} />} title='Повторяющихся задач нет' text='Откройте задачу → «Повтор» → «Настроить»' />
			) : (
				<div className='stack-s'>
					{data.map((s) => (
						<button key={s.id} className='member-row' onClick={() => s.task_id && navigate(`/task/${s.task_id}`)}>
							<span className='menu-icon'>
								<Repeat size={18} />
							</span>
							<span className='grow left'>
								<b>{s.title}</b>
								<span className='muted small block'>
									{s.describe} · {s.mode === 'schedule' ? 'по расписанию' : 'после выполнения'}
								</span>
							</span>
							<span className='muted small'>{s.next_run_at ? fmtDate(s.next_run_at) : 'ждёт выполнения'}</span>
						</button>
					))}
				</div>
			)}
		</div>
	)
}
