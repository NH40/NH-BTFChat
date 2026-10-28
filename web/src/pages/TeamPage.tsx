// Команда: роли и должности. Владелец назначает любые роли, старший — добавляет и убирает админов.
import { Plus, Trash2 } from 'lucide-react'
import { useEffect, useState } from 'react'
import { api, type Role, type StaffMember, type User } from '../api'
import { useStore } from '../store'
import { confirmAction } from '../tg'
import { Avatar, Field, Segmented, Sheet } from '../ui'
import { ROLE_NAMES } from '../util'

export default function TeamPage() {
	const { staff, me, run, reloadStaff } = useStore()
	const [adding, setAdding] = useState(false)
	const [editing, setEditing] = useState<StaffMember | null>(null)
	const canManage = (m: StaffMember): boolean => !m.fixed && m.id !== me?.id && Boolean(me?.is_owner || (me?.is_senior && m.role === 'admin'))

	return (
		<div className='page'>
			<header className='page-head'>
				<h2>Команда</h2>
				<span className='spacer' />
				{me?.is_senior && (
					<button className='btn primary small' onClick={() => setAdding(true)}>
						<Plus size={15} /> Добавить
					</button>
				)}
			</header>
			<div className='stack-s'>
				{staff.map((m) => (
					<button key={m.id} className='member-row' disabled={!canManage(m) && !me?.is_owner} onClick={() => setEditing(m)}>
						<Avatar user={m} size={36} />
						<span className='grow left'>
							<b>{m.name}</b>
							<span className='muted small block'>
								{m.username ? `@${m.username}` : m.id}
								{m.title && ` · ${m.title}`}
							</span>
						</span>
						<span className={`role-badge ${m.role}`}>{ROLE_NAMES[m.role]}</span>
					</button>
				))}
			</div>
			{adding && <AddSheet onClose={() => setAdding(false)} />}
			{editing && (
				<EditSheet
					member={editing}
					canRole={canManage(editing)}
					onClose={() => setEditing(null)}
					onRemove={async () => {
						if (!(await confirmAction(`Убрать ${editing.name} из команды?`))) return
						await run(() => api.del(`/staff/${editing.id}`), 'Убран из команды')
						await reloadStaff()
						setEditing(null)
					}}
				/>
			)}
		</div>
	)
}

function AddSheet({ onClose }: { onClose: () => void }) {
	const { me, run, reloadStaff } = useStore()
	const [q, setQ] = useState('')
	const [found, setFound] = useState<User[]>([])
	const [role, setRole] = useState<Role>('admin')
	const [title, setTitle] = useState('')

	useEffect(() => {
		if (q.trim().length < 2) return setFound([])
		const id = setTimeout(() => api.get<User[]>(`/users/search?q=${encodeURIComponent(q)}`).then(setFound).catch(() => setFound([])), 300)
		return () => clearTimeout(id)
	}, [q])

	const add = async (user: string) => {
		if (await run(() => api.post('/staff', { user, role, title: title || null }), 'Добавлен в команду')) {
			await reloadStaff()
			onClose()
		}
	}
	return (
		<Sheet title='Добавить в команду' onClose={onClose}>
			<div className='stack'>
				<Field label='Кого' hint='Человек должен хоть раз написать боту или в чат, где есть бот'>
					<input className='input' autoFocus placeholder='@username, имя или id' value={q} onChange={(e) => setQ(e.target.value)} />
				</Field>
				{me?.is_owner && (
					<Field label='Роль'>
						<Segmented
							value={role}
							options={[
								{ value: 'admin', label: 'Админ' },
								{ value: 'senior', label: 'Старший' },
								{ value: 'owner', label: 'Владелец' },
							]}
							onChange={setRole}
						/>
					</Field>
				)}
				<Field label='Должность / зона'>
					<input className='input' placeholder='Например: модерация чата, посты' value={title} onChange={(e) => setTitle(e.target.value)} maxLength={128} />
				</Field>
				<div className='stack-s'>
					{found.map((u) => (
						<button key={u.id} className='member-row' onClick={() => add(String(u.id))}>
							<Avatar user={u} size={30} />
							<span className='grow left'>
								<b>{u.name}</b>
								<span className='muted small block'>{u.username ? `@${u.username}` : u.id}</span>
							</span>
							<Plus size={16} />
						</button>
					))}
					{q.trim().length >= 2 && found.length === 0 && (
						<button className='btn ghost' onClick={() => add(q.trim())}>
							Добавить «{q.trim()}»
						</button>
					)}
				</div>
			</div>
		</Sheet>
	)
}

function EditSheet({ member, canRole, onClose, onRemove }: { member: StaffMember; canRole: boolean; onClose: () => void; onRemove: () => void }) {
	const { me, run, reloadStaff } = useStore()
	const [role, setRole] = useState<Role>(member.role)
	const [title, setTitle] = useState(member.title ?? '')
	const [notes, setNotes] = useState(member.notes ?? '')
	const save = async () => {
		const body: Record<string, unknown> = { title: title || null, notes: notes || null }
		if (canRole && role !== member.role) body.role = role
		if (await run(() => api.patch(`/staff/${member.id}`, body), 'Сохранено')) {
			await reloadStaff()
			onClose()
		}
	}
	return (
		<Sheet
			title={member.name}
			onClose={onClose}
			footer={
				<div className='row gap'>
					{canRole && (
						<button className='btn danger' onClick={onRemove}>
							<Trash2 size={15} />
						</button>
					)}
					<button className='btn primary grow' onClick={save}>
						Сохранить
					</button>
				</div>
			}
		>
			<div className='stack'>
				{canRole && me?.is_owner && (
					<Field label='Роль'>
						<Segmented
							value={role}
							options={[
								{ value: 'admin', label: 'Админ' },
								{ value: 'senior', label: 'Старший' },
								{ value: 'owner', label: 'Владелец' },
							]}
							onChange={setRole}
						/>
					</Field>
				)}
				{member.fixed && <div className='muted small'>Владелец из настроек сервера (OWNER_IDS) — роль не меняется.</div>}
				<Field label='Должность / зона'>
					<input className='input' value={title} onChange={(e) => setTitle(e.target.value)} maxLength={128} />
				</Field>
				<Field label='Заметки' hint='Видят только старшие и владелец'>
					<textarea className='input' rows={3} value={notes} onChange={(e) => setNotes(e.target.value)} />
				</Field>
			</div>
		</Sheet>
	)
}
