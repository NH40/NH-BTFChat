// Модерация одного чата: настройки антиспама и предупреждений, журнал, предупреждения, действия.
import { useEffect, useState } from 'react'
import { useParams } from 'react-router-dom'
import { api, type Chat, type User } from '../api'
import { useLoad, useStore } from '../store'
import { Avatar, Field, Section, Segmented, Spinner, Toggle } from '../ui'
import { fmtDate } from '../util'

type Action = 'delete' | 'warn' | 'mute' | 'ban'
interface Rule {
	enabled: boolean
	action: Action
	mute_minutes: number
}
interface ModSettings {
	enabled: boolean
	chat_admins_can_moderate: boolean
	ignore_staff: boolean
	warns: { limit: number; action: 'mute' | 'ban'; mute_minutes: number; expire_days: number }
	antiflood: Rule & { messages: number; seconds: number }
	links: Rule & { whitelist: string[] }
	words: Rule & { list: string[] }
	forwards: Rule
	welcome: { enabled: boolean; text: string; delete_after_seconds: number }
	rules: string
	log_actions: boolean
}

const ACTION_LABELS: Record<Action, string> = { delete: 'Удалить', warn: 'Предупредить', mute: 'Мут', ban: 'Бан' }

function RuleEditor<T extends Rule>({ title, hint, value, onChange, children }: { title: string; hint: string; value: T; onChange: (v: T) => void; children?: React.ReactNode }) {
	return (
		<Section title={title}>
			<Toggle checked={value.enabled} onChange={(enabled) => onChange({ ...value, enabled })} label={hint} />
			{value.enabled && (
				<>
					{children}
					<Field label='Действие'>
						<Segmented value={value.action} options={(Object.keys(ACTION_LABELS) as Action[]).map((a) => ({ value: a, label: ACTION_LABELS[a] }))} onChange={(action) => onChange({ ...value, action })} />
					</Field>
					{value.action === 'mute' && (
						<Field label='Мут, минут'>
							<input type='number' min={1} className='input narrow' value={value.mute_minutes} onChange={(e) => onChange({ ...value, mute_minutes: Number(e.target.value) })} />
						</Field>
					)}
				</>
			)}
		</Section>
	)
}

function SettingsTab({ chatId }: { chatId: number }) {
	const { run } = useStore()
	const { data, reload } = useLoad(() => api.get<{ chat: Chat; settings: ModSettings }>(`/chats/${chatId}/settings`), [chatId])
	const [s, setS] = useState<ModSettings | null>(null)
	useEffect(() => {
		if (data) setS(data.settings)
	}, [data])
	if (!s) return <Spinner />
	const set = <K extends keyof ModSettings>(key: K, value: ModSettings[K]) => setS({ ...s, [key]: value })
	return (
		<div className='stack'>
			<Section title='Общее'>
				<Toggle checked={s.enabled} onChange={(v) => set('enabled', v)} label='Антиспам включён' />
				<Toggle checked={s.chat_admins_can_moderate} onChange={(v) => set('chat_admins_can_moderate', v)} label='Админы чата могут /ban /mute (не только команда BTF)' />
				<Toggle checked={s.ignore_staff} onChange={(v) => set('ignore_staff', v)} label='Антиспам не трогает админов и команду' />
				<Toggle checked={s.log_actions} onChange={(v) => set('log_actions', v)} label='Писать в чат о наказаниях' />
			</Section>
			<Section title='Предупреждения'>
				<div className='grid2'>
					<Field label='Лимит'>
						<input type='number' min={1} className='input' value={s.warns.limit} onChange={(e) => set('warns', { ...s.warns, limit: Number(e.target.value) })} />
					</Field>
					<Field label='Сгорают через, дн' hint='0 — никогда'>
						<input type='number' min={0} className='input' value={s.warns.expire_days} onChange={(e) => set('warns', { ...s.warns, expire_days: Number(e.target.value) })} />
					</Field>
				</div>
				<Field label='На лимите'>
					<Segmented
						value={s.warns.action}
						options={[
							{ value: 'mute', label: 'Мут' },
							{ value: 'ban', label: 'Бан' },
						]}
						onChange={(action) => set('warns', { ...s.warns, action })}
					/>
				</Field>
				{s.warns.action === 'mute' && (
					<Field label='Мут, минут'>
						<input type='number' min={1} className='input narrow' value={s.warns.mute_minutes} onChange={(e) => set('warns', { ...s.warns, mute_minutes: Number(e.target.value) })} />
					</Field>
				)}
			</Section>
			<RuleEditor title='Антифлуд' hint='Ограничить частоту сообщений' value={s.antiflood} onChange={(v) => set('antiflood', v)}>
				<div className='row gap'>
					<input type='number' min={2} className='input narrow' value={s.antiflood.messages} onChange={(e) => set('antiflood', { ...s.antiflood, messages: Number(e.target.value) })} />
					<span className='muted small'>сообщений за</span>
					<input type='number' min={1} className='input narrow' value={s.antiflood.seconds} onChange={(e) => set('antiflood', { ...s.antiflood, seconds: Number(e.target.value) })} />
					<span className='muted small'>сек</span>
				</div>
			</RuleEditor>
			<RuleEditor title='Ссылки' hint='Запретить ссылки' value={s.links} onChange={(v) => set('links', v)}>
				<Field label='Разрешённые домены' hint='По одному в строке, например t.me/mychannel'>
					<textarea className='input' rows={3} value={s.links.whitelist.join('\n')} onChange={(e) => set('links', { ...s.links, whitelist: e.target.value.split('\n').map((x) => x.trim()).filter(Boolean) })} />
				</Field>
			</RuleEditor>
			<RuleEditor title='Стоп-слова' hint='Фильтр запрещённых слов' value={s.words} onChange={(v) => set('words', v)}>
				<Field label='Слова и фразы' hint='По одному в строке, регистр не важен'>
					<textarea className='input' rows={4} value={s.words.list.join('\n')} onChange={(e) => set('words', { ...s.words, list: e.target.value.split('\n').map((x) => x.trim()).filter(Boolean) })} />
				</Field>
			</RuleEditor>
			<RuleEditor title='Пересылки' hint='Запретить пересылки из чужих каналов и чатов' value={s.forwards} onChange={(v) => set('forwards', v)} />
			<Section title='Приветствие'>
				<Toggle checked={s.welcome.enabled} onChange={(enabled) => set('welcome', { ...s.welcome, enabled })} label='Приветствовать новичков' />
				{s.welcome.enabled && (
					<>
						<Field label='Текст' hint='{name} — имя, {username} — ник'>
							<textarea className='input' rows={3} value={s.welcome.text} onChange={(e) => set('welcome', { ...s.welcome, text: e.target.value })} />
						</Field>
						<Field label='Удалить через, сек' hint='0 — не удалять'>
							<input type='number' min={0} className='input narrow' value={s.welcome.delete_after_seconds} onChange={(e) => set('welcome', { ...s.welcome, delete_after_seconds: Number(e.target.value) })} />
						</Field>
					</>
				)}
			</Section>
			<Section title='Правила (/rules)'>
				<textarea className='input' rows={5} value={s.rules} onChange={(e) => set('rules', e.target.value)} placeholder='Текст правил чата' />
			</Section>
			<button className='btn primary block sticky-save' onClick={() => run(() => api.put(`/chats/${chatId}/settings`, s), 'Настройки сохранены').then(reload)}>
				Сохранить настройки
			</button>
		</div>
	)
}

interface ActionRow {
	id: number
	action: string
	reason: string | null
	until: string | null
	created_at: string
	target: User
	actor: User | null
}
const LOG_NAMES: Record<string, string> = { ban: 'бан', unban: 'разбан', mute: 'мут', unmute: 'размут', kick: 'кик', warn: 'предупреждение', unwarn: 'снято предупр.', delete: 'удалено сообщение' }

function LogTab({ chatId }: { chatId: number }) {
	const { data } = useLoad(() => api.get<ActionRow[]>(`/chats/${chatId}/actions?limit=100`), [chatId])
	if (!data) return <Spinner />
	if (!data.length) return <div className='muted small'>Журнал пуст</div>
	return (
		<div className='stack-s'>
			{data.map((a) => (
				<div key={a.id} className='log-row'>
					<span className={`log-tag ${a.action}`}>{LOG_NAMES[a.action] ?? a.action}</span>
					<span className='grow small'>
						<b>{a.target.name}</b>
						{a.reason && <span className='muted'> · {a.reason}</span>}
						{a.until && <span className='muted'> · до {fmtDate(a.until)}</span>}
						<span className='muted block tiny'>
							{fmtDate(a.created_at)} · {a.actor ? a.actor.name : 'автоматически'}
						</span>
					</span>
				</div>
			))}
		</div>
	)
}

function WarnsTab({ chatId }: { chatId: number }) {
	const { run } = useStore()
	const { data, reload } = useLoad(() => api.get<{ user: User; count: number; last_at: string }[]>(`/chats/${chatId}/warnings`), [chatId])
	if (!data) return <Spinner />
	if (!data.length) return <div className='muted small'>Активных предупреждений нет</div>
	return (
		<div className='stack-s'>
			{data.map((w) => (
				<div key={w.user.id} className='member-row static'>
					<Avatar user={w.user} size={28} />
					<span className='grow left small'>
						<b>{w.user.name}</b>
						<span className='muted block tiny'>последнее {fmtDate(w.last_at)}</span>
					</span>
					<span className='pct warn'>{w.count}</span>
					<button className='btn ghost small' onClick={() => run(() => api.post(`/chats/${chatId}/moderate`, { action: 'unwarn', user: String(w.user.id) }), 'Снято').then(reload)}>
						Снять
					</button>
				</div>
			))}
		</div>
	)
}

function ActTab({ chatId }: { chatId: number }) {
	const { run } = useStore()
	const [action, setAction] = useState('mute')
	const [user, setUser] = useState('')
	const [minutes, setMinutes] = useState('')
	const [reason, setReason] = useState('')
	const timed = action === 'ban' || action === 'mute'
	return (
		<div className='stack'>
			<Field label='Действие'>
				<select className='input' value={action} onChange={(e) => setAction(e.target.value)}>
					<option value='mute'>Мут</option>
					<option value='unmute'>Размут</option>
					<option value='ban'>Бан</option>
					<option value='unban'>Разбан</option>
					<option value='kick'>Исключить</option>
					<option value='warn'>Предупреждение</option>
					<option value='unwarn'>Снять предупреждение</option>
				</select>
			</Field>
			<Field label='Кому' hint='@username или числовой id'>
				<input className='input' value={user} onChange={(e) => setUser(e.target.value)} />
			</Field>
			{timed && (
				<Field label='Срок, минут' hint='Пусто — навсегда'>
					<input type='number' min={1} className='input narrow' value={minutes} onChange={(e) => setMinutes(e.target.value)} />
				</Field>
			)}
			{['ban', 'mute', 'kick', 'warn'].includes(action) && (
				<Field label='Причина'>
					<input className='input' value={reason} onChange={(e) => setReason(e.target.value)} maxLength={500} />
				</Field>
			)}
			<button
				className='btn primary'
				disabled={!user.trim()}
				onClick={() =>
					run(() => api.post(`/chats/${chatId}/moderate`, { action, user: user.trim(), minutes: timed && minutes ? Number(minutes) : null, reason: reason || null }), 'Готово').then(
						(ok) => ok && (setUser(''), setReason('')),
					)
				}
			>
				Применить
			</button>
		</div>
	)
}

export default function ChatPage() {
	const id = Number(useParams().id)
	const [tab, setTab] = useState<'settings' | 'log' | 'warns' | 'act'>('settings')
	return (
		<div className='page'>
			<header className='page-head'>
				<h2>Модерация</h2>
			</header>
			<Segmented
				value={tab}
				options={[
					{ value: 'settings', label: 'Настройки' },
					{ value: 'log', label: 'Журнал' },
					{ value: 'warns', label: 'Предупр.' },
					{ value: 'act', label: 'Действие' },
				]}
				onChange={setTab}
			/>
			{tab === 'settings' && <SettingsTab chatId={id} />}
			{tab === 'log' && <LogTab chatId={id} />}
			{tab === 'warns' && <WarnsTab chatId={id} />}
			{tab === 'act' && <ActTab chatId={id} />}
		</div>
	)
}
