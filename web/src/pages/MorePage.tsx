import { ChevronRight, MessagesSquare, Radio, Repeat, Settings, Users } from 'lucide-react'
import { Link } from 'react-router-dom'
import { useStore } from '../store'
import { ROLE_NAMES } from '../util'
import { Avatar } from '../ui'

export default function MorePage() {
	const { me } = useStore()
	const items = [
		{ to: '/team', icon: Users, title: 'Команда', text: 'Роли, должности, кто за что отвечает' },
		{ to: '/series', icon: Repeat, title: 'Повторы', text: 'Все цикличные задачи и когда появятся' },
		...(me?.is_senior
			? [
					{ to: '/chats', icon: MessagesSquare, title: 'Чаты и модерация', text: 'Назначение чатов, антиспам, баны, журнал' },
					{ to: '/relay', icon: Radio, title: 'Каналы', text: 'Пересылка постов из каналов в чаты' },
				]
			: []),
		{ to: '/settings', icon: Settings, title: 'Настройки', text: 'Напоминания по умолчанию, чат админов' },
	]
	return (
		<div className='page'>
			{me && (
				<div className='profile-card'>
					<Avatar user={me} size={44} />
					<div>
						<div className='hello-name'>{me.name}</div>
						<div className='muted small'>
							{ROLE_NAMES[me.role]}
							{me.username && ` · @${me.username}`}
						</div>
					</div>
				</div>
			)}
			<div className='stack-s'>
				{items.map((it) => (
					<Link key={it.to} to={it.to} className='menu-item'>
						<span className='menu-icon'>
							<it.icon size={20} />
						</span>
						<span className='grow'>
							<b>{it.title}</b>
							<span className='muted small block'>{it.text}</span>
						</span>
						<ChevronRight size={18} className='muted' />
					</Link>
				))}
			</div>
		</div>
	)
}
