// Даты и длительности в часовом поясе команды (приходит в /api/me).
let teamTz = 'Europe/Moscow'

export function setTimezone(tz: string): void {
	teamTz = tz
}

function parts(d: Date): Record<string, string> {
	const out: Record<string, string> = {}
	for (const p of new Intl.DateTimeFormat('ru-RU', {
		timeZone: teamTz,
		year: 'numeric',
		month: '2-digit',
		day: '2-digit',
		hour: '2-digit',
		minute: '2-digit',
		hourCycle: 'h23',
	}).formatToParts(d))
		out[p.type] = p.value
	return out
}

function dayKey(d: Date): string {
	const p = parts(d)
	return `${p.year}-${p.month}-${p.day}`
}

/** «сегодня 18:00», «завтра 10:00», «12.11 09:30». */
export function fmtDate(iso: string | null | undefined): string {
	if (!iso) return '—'
	const d = new Date(iso)
	const p = parts(d)
	const time = `${p.hour}:${p.minute}`
	const now = new Date()
	const key = dayKey(d)
	if (key === dayKey(now)) return `сегодня ${time}`
	if (key === dayKey(new Date(now.getTime() + 86400000))) return `завтра ${time}`
	if (key === dayKey(new Date(now.getTime() - 86400000))) return `вчера ${time}`
	const year = p.year !== parts(now).year ? `.${p.year.slice(2)}` : ''
	return `${p.day}.${p.month}${year} ${time}`
}

export function fmtDay(isoDate: string): string {
	const [, m, d] = isoDate.split('-')
	return `${d}.${m}`
}

/** ISO → значение для <input type="datetime-local"> во времени команды. */
export function toInput(iso: string | null | undefined): string {
	if (!iso) return ''
	// Ещё не сохранённое значение из формы — уже время команды, без пояса.
	if (!/(Z|[+-]\d\d:?\d\d)$/.test(iso)) return iso.slice(0, 16)
	const p = parts(new Date(iso))
	return `${p.year}-${p.month}-${p.day}T${p.hour}:${p.minute}`
}

/** Значение datetime-local → строка без пояса (сервер считает её временем команды). */
export function fromInput(value: string): string | null {
	return value ? `${value}:00` : null
}

/** Через сколько / сколько назад: «через 2 ч», «просрочено 3 д». */
export function relative(iso: string | null | undefined): string {
	if (!iso) return ''
	const diff = new Date(iso).getTime() - Date.now()
	const abs = Math.abs(diff) / 60000
	const txt = abs < 60 ? `${Math.max(1, Math.round(abs))} мин` : abs < 1440 ? `${Math.round(abs / 60)} ч` : `${Math.round(abs / 1440)} д`
	return diff >= 0 ? `через ${txt}` : `${txt} назад`
}

export function duration(seconds: number): string {
	if (!seconds) return '0 мин'
	const h = Math.floor(seconds / 3600)
	const m = Math.round((seconds % 3600) / 60)
	if (!h) return `${m} мин`
	return m ? `${h} ч ${m} мин` : `${h} ч`
}

export function clock(seconds: number): string {
	const h = Math.floor(seconds / 3600)
	const m = Math.floor((seconds % 3600) / 60)
	const s = Math.floor(seconds % 60)
	return `${h}:${String(m).padStart(2, '0')}:${String(s).padStart(2, '0')}`
}

export function minutesLabel(min: number | null | undefined): string {
	if (!min) return '0 мин'
	if (min % 1440 === 0) return `${min / 1440} д`
	if (min % 60 === 0) return `${min / 60} ч`
	return `${min} мин`
}

export const PRIORITIES = [
	{ value: 0, label: 'Низкий', color: '#7d8799' },
	{ value: 1, label: 'Обычный', color: '#5b8cff' },
	{ value: 2, label: 'Высокий', color: '#f5a524' },
	{ value: 3, label: 'Срочно', color: '#f04f5f' },
]

export const ROLE_NAMES: Record<string, string> = { owner: 'Владелец', senior: 'Старший', admin: 'Админ' }

export function initials(name: string): string {
	return (
		name
			.split(/\s+/)
			.filter(Boolean)
			.slice(0, 2)
			.map((w) => w[0]?.toUpperCase())
			.join('') || '?'
	)
}

export function colorFor(id: number): string {
	const palette = ['#5b8cff', '#22c3a6', '#f5a524', '#c46bff', '#ff6b8b', '#4cc9f0', '#8bd450', '#ff8a4c']
	return palette[Math.abs(id) % palette.length]
}
