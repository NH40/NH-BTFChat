// Пересылка: для каждого канала — в какие чаты пересылать; проверка удалений; последние посты.
import { Radio } from 'lucide-react'
import { useEffect, useState } from 'react'
import { api, type Chat } from '../api'
import { useLoad, useStore } from '../store'
import { Empty, Field, Section, Spinner, Toggle } from '../ui'
import { fmtDate } from '../util'

interface Overview {
	channels: (Chat & { posts: number; targets: number[] })[]
	targets: Chat[]
	service_chat: Chat | null
	check: { enabled: boolean; window_hours: number; interval_minutes: number; batch: number }
}
interface Post {
	id: number
	channel: string | null
	message_id: number
	parts: number
	version: number
	deleted: boolean
	copies: number
	created_at: string
	last_checked_at: string
}

export default function RelayPage() {
	const { run } = useStore()
	const { data, reload, loading } = useLoad(() => api.get<Overview>('/relay'), [])
	const posts = useLoad(() => api.get<Post[]>('/relay/posts?limit=20'), [])
	const [check, setCheck] = useState<Overview['check'] | null>(null)
	useEffect(() => {
		if (data) setCheck(data.check)
	}, [data])

	if (loading || !data || !check) return <Spinner />

	const toggle = async (channel: Overview['channels'][number], target: number) => {
		const ids = channel.targets.includes(target) ? channel.targets.filter((x) => x !== target) : [...channel.targets, target]
		await run(() => api.put(`/relay/channels/${channel.id}`, { target_ids: ids }), 'Сохранено')
		await reload()
	}

	return (
		<div className='page'>
			<header className='page-head'>
				<h2>Каналы</h2>
			</header>
			<div className='hint-card small'>
				Новый пост пересылается («Переслано из…») во все отмеченные чаты. Правка в канале — старая пересылка удаляется, свежая версия приходит заново. Удаление в канале — пересылки удаляются в
				чатах.
			</div>
			{data.channels.length === 0 ? (
				<Empty icon={<Radio size={36} />} title='Каналов нет' text='Добавьте бота администратором в канал' />
			) : (
				data.channels.map((ch) => (
					<Section key={ch.id} title={ch.title}>
						{ch.bot_status !== 'administrator' && <div className='warn-text small'>Бот не админ канала — посты не приходят</div>}
						{data.targets.length === 0 && <div className='muted small'>Нет групп с ботом</div>}
						{data.targets.map((t) => (
							<Toggle key={t.id} checked={ch.targets.includes(t.id)} onChange={() => toggle(ch, t.id)} label={t.title} />
						))}
						<div className='muted tiny'>Отслеживается постов: {ch.posts}</div>
					</Section>
				))
			)}
			<Section title='Проверка удалений'>
				<div className='small'>
					Служебный чат: {data.service_chat ? <b>{data.service_chat.title}</b> : <span className='danger-text'>не выбран (раздел «Чаты»)</span>}
				</div>
				<Toggle checked={check.enabled} onChange={(enabled) => setCheck({ ...check, enabled })} label='Проверять, не удалён ли пост в канале' />
				<div className='grid2'>
					<Field label='Следить за постами, ч' hint='Посты старше не проверяются'>
						<input type='number' min={1} className='input' value={check.window_hours} onChange={(e) => setCheck({ ...check, window_hours: Number(e.target.value) })} />
					</Field>
					<Field label='Каждый пост раз в, мин'>
						<input type='number' min={5} className='input' value={check.interval_minutes} onChange={(e) => setCheck({ ...check, interval_minutes: Number(e.target.value) })} />
					</Field>
				</div>
				<button className='btn primary' onClick={() => run(() => api.put('/relay/check', check), 'Сохранено').then(reload)}>
					Сохранить
				</button>
			</Section>
			<Section title='Последние посты'>
				{!posts.data?.length && <div className='muted small'>Пока ничего не пересылалось</div>}
				{posts.data?.map((p) => (
					<div key={p.id} className='log-row'>
						<span className={`log-tag ${p.deleted ? 'ban' : 'ok'}`}>{p.deleted ? 'удалён' : `в ${p.copies} чат.`}</span>
						<span className='grow small'>
							<b>{p.channel}</b> #{p.message_id}
							{p.parts > 1 && <span className='muted'> · альбом {p.parts}</span>}
							{p.version > 1 && <span className='muted'> · правок {p.version - 1}</span>}
							<span className='muted block tiny'>
								{fmtDate(p.created_at)} · проверен {fmtDate(p.last_checked_at)}
							</span>
						</span>
					</div>
				))}
			</Section>
		</div>
	)
}
