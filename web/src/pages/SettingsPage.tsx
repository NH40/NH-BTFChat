import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { api, type Chat, type Reminder } from '../api'
import ReminderEditor from '../components/ReminderEditor'
import { useLoad, useStore } from '../store'
import { Section, Spinner } from '../ui'

interface AppSettings {
	timezone: string
	admin_chat: Chat | null
	service_chat: Chat | null
	reminder_defaults: Reminder[]
}

export default function SettingsPage() {
	const { me, run } = useStore()
	const { data, reload, loading } = useLoad(() => api.get<AppSettings>('/settings'), [])
	const [items, setItems] = useState<Reminder[]>([])
	useEffect(() => {
		if (data) setItems(data.reminder_defaults)
	}, [data])
	if (loading || !data) return <Spinner />
	return (
		<div className='page'>
			<header className='page-head'>
				<h2>Настройки</h2>
			</header>
			<Section title='Чат админов'>
				<div className='small'>
					{data.admin_chat ? <b>{data.admin_chat.title}</b> : <span className='danger-text'>Не выбран — напоминания никуда не уходят</span>}
				</div>
				<div className='muted small'>Сюда бот шлёт напоминания и новые задачи с @упоминаниями исполнителей.</div>
				{me?.is_senior && (
					<Link to='/chats' className='btn ghost small'>
						Выбрать в «Чатах»
					</Link>
				)}
			</Section>
			<Section title='Служебный чат'>
				<div className='small'>{data.service_chat ? <b>{data.service_chat.title}</b> : <span className='muted'>Не выбран — удаления постов в каналах не отслеживаются</span>}</div>
				<div className='muted small'>Отдельная группа только с ботом: туда бот пересылает посты, чтобы проверить, не удалены ли они в канале. Сообщения там просто копятся.</div>
			</Section>
			<Section title='Напоминания по умолчанию'>
				<div className='muted small'>Ставятся каждой новой задаче с дедлайном, если при создании не выбраны свои.</div>
				<ReminderEditor items={items} onChange={setItems} allowAt={false} />
				{me?.is_senior && (
					<button className='btn primary' onClick={() => run(() => api.put('/settings/reminder-defaults', { items }), 'Сохранено').then(reload)}>
						Сохранить
					</button>
				)}
			</Section>
			<Section title='Часовой пояс команды'>
				<div className='small'>{data.timezone}</div>
				<div className='muted small'>Все сроки, повторы и отчёты — в этом поясе. Меняется в .env (TIMEZONE).</div>
			</Section>
		</div>
	)
}
