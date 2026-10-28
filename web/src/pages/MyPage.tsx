// Мои задачи: сгруппированы по сроку — просрочено, сегодня, неделя, позже, без срока.
import { PartyPopper } from 'lucide-react'
import { useNavigate } from 'react-router-dom'
import { api, type TaskCard } from '../api'
import TaskCardView from '../components/TaskCardView'
import { useLoad, useStore } from '../store'
import { Empty, Spinner } from '../ui'
import { ROLE_NAMES } from '../util'

function bucket(t: TaskCard): number {
	if (!t.deadline) return 4
	const diff = new Date(t.deadline).getTime() - Date.now()
	if (diff < 0) return 0
	const end = new Date()
	end.setHours(23, 59, 59, 999)
	if (new Date(t.deadline) <= end) return 1
	if (diff < 7 * 86400000) return 2
	return 3
}

const GROUPS = ['Просрочено', 'Сегодня', 'На этой неделе', 'Позже', 'Без срока']

export default function MyPage() {
	const { me, boards } = useStore()
	const navigate = useNavigate()
	const { data, loading } = useLoad(() => api.get<TaskCard[]>('/tasks/mine'), [])
	const labels = boards.flatMap((b) => b.labels)
	const groups: TaskCard[][] = GROUPS.map(() => [])
	for (const t of data ?? []) groups[bucket(t)].push(t)

	return (
		<div className='page'>
			<header className='hello'>
				<div className='hello-name'>{me?.name}</div>
				<div className='muted small'>
					{ROLE_NAMES[me?.role ?? 'admin']} · {me?.open_tasks ?? 0} открытых
					{me?.overdue_tasks ? <span className='danger-text'> · {me.overdue_tasks} просрочено</span> : null}
				</div>
			</header>
			{loading ? (
				<Spinner />
			) : !data?.length ? (
				<Empty icon={<PartyPopper size={36} />} title='Открытых задач нет' text='Всё сделано — можно взять что-нибудь с доски' />
			) : (
				groups.map(
					(list, i) =>
						list.length > 0 && (
							<section key={i} className='my-group'>
								<h4 className={i === 0 ? 'danger-text' : ''}>
									{GROUPS[i]} <span className='muted'>{list.length}</span>
								</h4>
								<div className='stack-s'>
									{list.map((t) => (
										<TaskCardView key={t.id} task={t} labels={labels} onClick={() => navigate(`/task/${t.id}`)} />
									))}
								</div>
							</section>
						),
				)
			)}
		</div>
	)
}
