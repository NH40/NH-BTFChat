import { AlarmClock, CheckSquare, MessageSquare, Repeat, Timer } from 'lucide-react'
import type { Label, TaskCard } from '../api'
import { AvatarStack } from '../ui'
import { fmtDate, PRIORITIES } from '../util'

export function deadlineTone(task: TaskCard): string {
	if (!task.deadline || task.completed_at) return ''
	if (task.overdue) return 'danger'
	return new Date(task.deadline).getTime() - Date.now() < 86400000 ? 'warn' : ''
}

export default function TaskCardView({ task, labels, onClick, dragging }: { task: TaskCard; labels: Label[]; onClick?: () => void; dragging?: boolean }) {
	const prio = PRIORITIES[task.priority] ?? PRIORITIES[1]
	const taskLabels = labels.filter((l) => task.label_ids.includes(l.id))
	return (
		<div className={`task-card ${dragging ? 'dragging' : ''} ${task.completed_at ? 'done' : ''}`} onClick={onClick}>
			<span className='prio-stripe' style={{ background: prio.color }} />
			{taskLabels.length > 0 && (
				<div className='card-labels'>
					{taskLabels.map((l) => (
						<span key={l.id} className='label-dot' style={{ background: l.color }}>
							{l.name}
						</span>
					))}
				</div>
			)}
			<div className='card-title'>{task.title}</div>
			<div className='card-meta'>
				{task.deadline && (
					<span className={`chip ${deadlineTone(task)} ${task.deadline_hard ? '' : 'soft'}`}>
						<AlarmClock size={12} />
						{fmtDate(task.deadline)}
					</span>
				)}
				{task.checklist.total > 0 && (
					<span className={`chip ${task.checklist.done === task.checklist.total ? 'ok' : ''}`}>
						<CheckSquare size={12} />
						{task.checklist.done}/{task.checklist.total}
					</span>
				)}
				{task.comments > 0 && (
					<span className='chip'>
						<MessageSquare size={12} />
						{task.comments}
					</span>
				)}
				{task.series_id && (
					<span className='chip' title='Повторяется'>
						<Repeat size={12} />
					</span>
				)}
				{task.timer_running && (
					<span className='chip live' title='Идёт таймер'>
						<Timer size={12} />
					</span>
				)}
				<span className='spacer' />
				{task.assignees.length > 0 && <AvatarStack users={task.assignees} />}
			</div>
		</div>
	)
}
