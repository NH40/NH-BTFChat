import { BarChart3, CheckSquare, KanbanSquare, LayoutGrid, ShieldAlert } from 'lucide-react'
import { useEffect } from 'react'
import { NavLink, Route, Routes, useLocation, useNavigate } from 'react-router-dom'
import TimerBar from './components/TimerBar'
import BoardPage from './pages/BoardPage'
import ChatPage from './pages/ChatPage'
import ChatsPage from './pages/ChatsPage'
import MorePage from './pages/MorePage'
import MyPage from './pages/MyPage'
import RelayPage from './pages/RelayPage'
import ReportsPage from './pages/ReportsPage'
import SeriesPage from './pages/SeriesPage'
import SettingsPage from './pages/SettingsPage'
import TaskPage from './pages/TaskPage'
import TeamPage from './pages/TeamPage'
import { useStore } from './store'
import { backButton, insideTelegram } from './tg'
import { Empty, Spinner } from './ui'

const TABS = [
	{ to: '/', label: 'Доска', icon: KanbanSquare, end: true },
	{ to: '/my', label: 'Мои', icon: CheckSquare },
	{ to: '/reports', label: 'Отчёты', icon: BarChart3 },
	{ to: '/more', label: 'Ещё', icon: LayoutGrid },
]
const ROOTS = new Set(TABS.map((t) => t.to))

export default function App() {
	const { me, error, toasts } = useStore()
	const location = useLocation()
	const navigate = useNavigate()

	// Нативная кнопка «Назад» Telegram на всех экранах, кроме корневых вкладок.
	useEffect(() => {
		if (ROOTS.has(location.pathname)) return backButton(null)
		return backButton(() => (window.history.length > 1 ? navigate(-1) : navigate('/')))
	}, [location.pathname, navigate])

	if (error) {
		return (
			<div className='screen-center'>
				<Empty
					icon={<ShieldAlert size={36} />}
					title={insideTelegram() ? 'Нет доступа' : 'Откройте через Telegram'}
					text={insideTelegram() ? error : 'Mini App BTF работает только внутри Telegram — кнопка в боте.'}
				/>
			</div>
		)
	}
	if (!me) {
		return (
			<div className='screen-center'>
				<Spinner />
			</div>
		)
	}

	return (
		<div className='app'>
			<TimerBar />
			<main className='content'>
				<Routes>
					<Route path='/' element={<BoardPage />} />
					<Route path='/my' element={<MyPage />} />
					<Route path='/reports' element={<ReportsPage />} />
					<Route path='/more' element={<MorePage />} />
					<Route path='/task/:id' element={<TaskPage />} />
					<Route path='/team' element={<TeamPage />} />
					<Route path='/series' element={<SeriesPage />} />
					<Route path='/settings' element={<SettingsPage />} />
					{me.is_senior && <Route path='/chats' element={<ChatsPage />} />}
					{me.is_senior && <Route path='/chats/:id' element={<ChatPage />} />}
					{me.is_senior && <Route path='/relay' element={<RelayPage />} />}
					<Route path='*' element={<Empty title='Страница не найдена' />} />
				</Routes>
			</main>
			<nav className='tabbar'>
				{TABS.map((t) => (
					<NavLink key={t.to} to={t.to} end={t.end} className={({ isActive }) => `tab ${isActive ? 'active' : ''}`}>
						<t.icon size={20} />
						<span>{t.label}</span>
						{t.to === '/my' && me.overdue_tasks > 0 && <span className='tab-badge'>{me.overdue_tasks}</span>}
					</NavLink>
				))}
			</nav>
			<div className='toasts'>
				{toasts.map((t) => (
					<div key={t.id} className={`toast ${t.kind}`}>
						{t.text}
					</div>
				))}
			</div>
		</div>
	)
}
