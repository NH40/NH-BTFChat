// Мелкие общие компоненты интерфейса.
import { X } from 'lucide-react'
import { useEffect, type ReactNode } from 'react'
import type { StaffMember, User } from './api'
import { colorFor, initials } from './util'

export function Avatar({ user, size = 26 }: { user: User; size?: number }) {
	return (
		<span className='avatar' title={user.name} style={{ width: size, height: size, fontSize: size * 0.4, background: colorFor(user.id) }}>
			{initials(user.name)}
		</span>
	)
}

export function AvatarStack({ users, max = 3 }: { users: User[]; max?: number }) {
	const shown = users.slice(0, max)
	return (
		<span className='avatar-stack'>
			{shown.map((u) => (
				<Avatar key={u.id} user={u} size={22} />
			))}
			{users.length > max && <span className='avatar more'>+{users.length - max}</span>}
		</span>
	)
}

export function Spinner() {
	return <div className='spinner' aria-label='Загрузка' />
}

export function Empty({ icon, title, text }: { icon?: ReactNode; title: string; text?: string }) {
	return (
		<div className='empty'>
			{icon && <div className='empty-icon'>{icon}</div>}
			<div className='empty-title'>{title}</div>
			{text && <div className='empty-text'>{text}</div>}
		</div>
	)
}

export function Sheet({ title, onClose, children, footer }: { title: string; onClose: () => void; children: ReactNode; footer?: ReactNode }) {
	useEffect(() => {
		const onKey = (e: KeyboardEvent) => e.key === 'Escape' && onClose()
		window.addEventListener('keydown', onKey)
		document.body.style.overflow = 'hidden'
		return () => {
			window.removeEventListener('keydown', onKey)
			document.body.style.overflow = ''
		}
	}, [onClose])
	return (
		<div className='sheet-backdrop' onClick={onClose}>
			<div className='sheet' onClick={(e) => e.stopPropagation()} role='dialog' aria-label={title}>
				<div className='sheet-head'>
					<h3>{title}</h3>
					<button className='icon-btn' onClick={onClose} aria-label='Закрыть'>
						<X size={18} />
					</button>
				</div>
				<div className='sheet-body'>{children}</div>
				{footer && <div className='sheet-foot'>{footer}</div>}
			</div>
		</div>
	)
}

export function Field({ label, hint, children }: { label: string; hint?: string; children: ReactNode }) {
	return (
		<label className='field'>
			<span className='field-label'>{label}</span>
			{children}
			{hint && <span className='field-hint'>{hint}</span>}
		</label>
	)
}

export function Toggle({ checked, onChange, label }: { checked: boolean; onChange: (v: boolean) => void; label: ReactNode }) {
	return (
		<label className='toggle'>
			<span>{label}</span>
			<input type='checkbox' checked={checked} onChange={(e) => onChange(e.target.checked)} />
			<span className='toggle-track' />
		</label>
	)
}

export function Segmented<T extends string | number>({ value, options, onChange }: { value: T; options: { value: T; label: string }[]; onChange: (v: T) => void }) {
	return (
		<div className='segmented'>
			{options.map((o) => (
				<button key={String(o.value)} className={o.value === value ? 'active' : ''} onClick={() => onChange(o.value)} type='button'>
					{o.label}
				</button>
			))}
		</div>
	)
}

/** Выбор людей из команды (несколько). */
export function PeoplePicker({ staff, value, onChange, single }: { staff: StaffMember[]; value: number[]; onChange: (ids: number[]) => void; single?: boolean }) {
	return (
		<div className='people-picker'>
			{staff.map((s) => {
				const on = value.includes(s.id)
				return (
					<button
						type='button'
						key={s.id}
						className={`person-chip ${on ? 'on' : ''}`}
						onClick={() => onChange(single ? (on ? [] : [s.id]) : on ? value.filter((x) => x !== s.id) : [...value, s.id])}
					>
						<Avatar user={s} size={20} />
						<span>{s.name}</span>
					</button>
				)
			})}
		</div>
	)
}

export function Section({ title, action, children }: { title: string; action?: ReactNode; children: ReactNode }) {
	return (
		<section className='section'>
			<div className='section-head'>
				<h4>{title}</h4>
				{action}
			</div>
			{children}
		</section>
	)
}
