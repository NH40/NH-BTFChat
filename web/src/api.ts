// Клиент API: каждый запрос подписан initData Telegram (сервер проверяет HMAC).
import { initData } from './tg'

export type Role = 'owner' | 'senior' | 'admin'

export interface User {
	id: number
	name: string
	username: string | null
}

export interface Me extends User {
	role: Role
	is_senior: boolean
	is_owner: boolean
	timezone: string
	open_tasks: number
	overdue_tasks: number
	timer: { task_id: number; title: string; started_at: string } | null
}

export interface Column {
	id: number
	name: string
	position: number
	is_done: boolean
	wip_limit: number | null
	open_count: number
}

export interface Label {
	id: number
	name: string
	color: string
}

export interface Board {
	id: number
	name: string
	description: string | null
	color: string
	archived: boolean
	columns: Column[]
	labels: Label[]
	open_count: number
}

export interface TaskCard {
	id: number
	board_id: number
	column_id: number
	title: string
	priority: number
	label_ids: number[]
	position: number
	deadline: string | null
	deadline_hard: boolean
	start_at: string | null
	overdue: boolean
	completed_at: string | null
	archived: boolean
	series_id: number | null
	assignees: User[]
	checklist: { total: number; done: number }
	comments: number
	time_seconds: number
	timer_running: boolean
	estimate_minutes: number | null
}

export type ReminderKind = 'before' | 'at' | 'repeat' | 'overdue'

export interface Reminder {
	id?: number
	kind: ReminderKind
	offset_minutes?: number | null
	at?: string | null
	interval_minutes?: number | null
	text?: string | null
	next_at?: string | null
	sent_count?: number
	active?: boolean
}

export interface SeriesRule {
	type: 'interval' | 'weekly' | 'monthly'
	n?: number
	unit?: 'hours' | 'days'
	start?: string
	weekdays?: number[]
	day?: number
	time?: string
}

export interface TaskDetail extends TaskCard {
	description: string | null
	created_at: string
	created_by: User | null
	completed_by: User | null
	can_edit: boolean
	checklist_items: { id: number; text: string; done: boolean; assignee: User | null; deadline: string | null; done_at: string | null }[]
	comment_list: { id: number; user: User; text: string; created_at: string }[]
	history: { id: number; user: User | null; action: string; data: Record<string, unknown>; created_at: string }[]
	reminders: Reminder[]
	time_entries: { id: number; user: User; started_at: string; ended_at: string | null; seconds: number | null; note: string | null }[]
	time_by_user: { user: User; seconds: number }[]
	series: null | {
		id: number
		rule: SeriesRule
		mode: 'schedule' | 'after_done'
		deadline_minutes: number | null
		rotate: boolean
		rotation: User[]
		next_run_at: string | null
		ends_at: string | null
		describe: string
	}
}

export interface StaffMember extends User {
	role: Role
	title: string | null
	notes: string | null
	fixed: boolean
}

export interface Chat {
	id: number
	title: string
	username: string | null
	type: string
	kind: 'none' | 'community' | 'admin' | 'service' | 'channel'
	bot_status: string
	routes_out?: number
	routes_in?: number
}

export interface Report {
	from: string
	to: string
	totals: { completed: number; on_time: number; late: number; seconds: number; open: number; overdue: number }
	members: {
		user: User
		completed: number
		on_time: number
		late: number
		on_time_pct: number | null
		avg_hours: number | null
		open: number
		overdue: number
		seconds: number
	}[]
	days: { date: string; completed: number; created: number }[]
}

export class ApiError extends Error {
	status: number
	constructor(status: number, message: string) {
		super(message)
		this.status = status
	}
}

async function request<T>(method: string, path: string, body?: unknown): Promise<T> {
	const res = await fetch(`/api${path}`, {
		method,
		headers: { 'Content-Type': 'application/json', 'X-Telegram-Init-Data': initData() },
		body: body === undefined ? undefined : JSON.stringify(body),
	})
	if (!res.ok) {
		let detail = `Ошибка ${res.status}`
		try {
			const data = await res.json()
			if (typeof data.detail === 'string') detail = data.detail
			else if (Array.isArray(data.detail)) detail = 'Проверьте заполнение полей'
		} catch {
			/* не JSON */
		}
		throw new ApiError(res.status, detail)
	}
	return res.json() as Promise<T>
}

export const api = {
	get: <T>(path: string) => request<T>('GET', path),
	post: <T = { ok: boolean }>(path: string, body?: unknown) => request<T>('POST', path, body ?? {}),
	put: <T = { ok: boolean }>(path: string, body: unknown) => request<T>('PUT', path, body),
	patch: <T = { ok: boolean }>(path: string, body: unknown) => request<T>('PATCH', path, body),
	del: <T = { ok: boolean }>(path: string) => request<T>('DELETE', path),
}
