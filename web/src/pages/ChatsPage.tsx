// Чаты, где есть бот: назначение каждого (сообщество / чат админов / служебный / канал).
import { AlertTriangle, ChevronRight, MessagesSquare } from 'lucide-react'
import { useNavigate } from 'react-router-dom'
import { api, type Chat } from '../api'
import { useLoad, useStore } from '../store'
import { confirmAction } from '../tg'
import { Empty, Spinner } from '../ui'

const KIND_LABELS: Record<Chat['kind'], string> = {
	none: 'Без назначения',
	community: 'Сообщество (модерация, получает посты)',
	admin: 'Чат админов (напоминания)',
	service: 'Служебный (проверка постов)',
	channel: 'Канал-источник',
}

export default function ChatsPage() {
	const { run } = useStore()
	const navigate = useNavigate()
	const { data, reload, loading } = useLoad(() => api.get<Chat[]>('/chats'), [])

	const setKind = async (chat: Chat, kind: Chat['kind']) => {
		await run(() => api.put(`/chats/${chat.id}/kind`, { kind }), 'Сохранено')
		await reload()
	}

	return (
		<div className='page'>
			<header className='page-head'>
				<h2>Чаты</h2>
			</header>
			<div className='hint-card small'>
				Добавьте бота в группу или канал администратором — чат появится здесь. Чат админов и служебный — по одному: выбор нового снимает прежний.
			</div>
			{loading ? (
				<Spinner />
			) : !data?.length ? (
				<Empty icon={<MessagesSquare size={36} />} title='Бот пока ни в одном чате' />
			) : (
				<div className='stack-s'>
					{data.map((c) => (
						<div key={c.id} className={`chat-row ${c.bot_status === 'left' ? 'left' : ''}`}>
							<div className='row gap'>
								<b className='grow'>{c.title}</b>
								<span className='muted tiny'>{c.type === 'channel' ? 'канал' : 'группа'}</span>
							</div>
							{c.bot_status === 'left' ? (
								<div className='row gap small'>
									<span className='muted grow'>Бот вышел из чата</span>
									<button className='btn ghost small' onClick={async () => (await confirmAction('Убрать чат из списка?')) && run(() => api.del(`/chats/${c.id}`)).then(reload)}>
										Убрать
									</button>
								</div>
							) : (
								<>
									{c.bot_status !== 'administrator' && (
										<div className='warn-text small row gap-s'>
											<AlertTriangle size={13} /> Бот не админ — модерация и пересылка не сработают
										</div>
									)}
									<div className='row gap'>
										<select className='input' value={c.kind} onChange={(e) => setKind(c, e.target.value as Chat['kind'])}>
											{(c.type === 'channel' ? (['none', 'channel'] as const) : (['none', 'community', 'admin', 'service'] as const)).map((k) => (
												<option key={k} value={k}>
													{KIND_LABELS[k]}
												</option>
											))}
										</select>
										{c.kind === 'community' && (
											<button className='btn' onClick={() => navigate(`/chats/${c.id}`)} aria-label='Модерация'>
												<ChevronRight size={16} />
											</button>
										)}
									</div>
									{c.routes_in || c.routes_out ? (
										<div className='muted tiny'>{c.type === 'channel' ? `пересылается в ${c.routes_out} чат(ов)` : `получает посты из ${c.routes_in} канал(ов)`}</div>
									) : null}
								</>
							)}
						</div>
					))}
				</div>
			)}
		</div>
	)
}
