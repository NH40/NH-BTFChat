// Полоса идущего таймера: видна на любом экране, тап — к задаче, кнопка — стоп.
import { Square, Timer } from 'lucide-react'
import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { api } from '../api'
import { useStore } from '../store'
import { clock } from '../util'

export default function TimerBar() {
	const { me, reloadMe, run } = useStore()
	const navigate = useNavigate()
	const [, tick] = useState(0)
	useEffect(() => {
		if (!me?.timer) return
		const id = setInterval(() => tick((x) => x + 1), 1000)
		return () => clearInterval(id)
	}, [me?.timer])
	if (!me?.timer) return null
	const elapsed = (Date.now() - new Date(me.timer.started_at).getTime()) / 1000
	return (
		<div className='timer-bar' onClick={() => navigate(`/task/${me.timer!.task_id}`)}>
			<Timer size={16} className='pulse' />
			<span className='timer-title'>{me.timer.title}</span>
			<span className='timer-clock'>{clock(elapsed)}</span>
			<button
				className='icon-btn small'
				aria-label='Остановить таймер'
				onClick={async (e) => {
					e.stopPropagation()
					await run(() => api.post('/timer/stop'), 'Время записано')
					await reloadMe()
				}}
			>
				<Square size={14} />
			</button>
		</div>
	)
}
