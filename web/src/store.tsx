// Общее состояние приложения: я, команда, доски, тосты. Без сторонних стейт-библиотек.
import { createContext, useCallback, useContext, useEffect, useMemo, useRef, useState, type ReactNode } from 'react'
import { api, type Board, type Me, type StaffMember } from './api'
import { haptic } from './tg'
import { setTimezone } from './util'

interface Toast {
	id: number
	text: string
	kind: 'ok' | 'error'
}

interface Store {
	me: Me | null
	staff: StaffMember[]
	boards: Board[]
	error: string | null
	reloadMe(): Promise<void>
	reloadStaff(): Promise<void>
	reloadBoards(): Promise<void>
	toast(text: string, kind?: 'ok' | 'error'): void
	run<T>(action: () => Promise<T>, ok?: string): Promise<T | undefined>
	toasts: Toast[]
}

const Ctx = createContext<Store | null>(null)

export function StoreProvider({ children }: { children: ReactNode }) {
	const [me, setMe] = useState<Me | null>(null)
	const [staff, setStaff] = useState<StaffMember[]>([])
	const [boards, setBoards] = useState<Board[]>([])
	const [error, setError] = useState<string | null>(null)
	const [toasts, setToasts] = useState<Toast[]>([])
	const seq = useRef(0)

	const toast = useCallback((text: string, kind: 'ok' | 'error' = 'ok') => {
		const id = ++seq.current
		setToasts((t) => [...t, { id, text, kind }])
		haptic(kind === 'ok' ? 'success' : 'error')
		setTimeout(() => setToasts((t) => t.filter((x) => x.id !== id)), 2800)
	}, [])

	const reloadMe = useCallback(async () => {
		const data = await api.get<Me>('/me')
		setTimezone(data.timezone)
		setMe(data)
	}, [])
	const reloadStaff = useCallback(async () => setStaff(await api.get<StaffMember[]>('/staff')), [])
	const reloadBoards = useCallback(async () => setBoards(await api.get<Board[]>('/boards')), [])

	const run = useCallback(
		async <T,>(action: () => Promise<T>, ok?: string) => {
			try {
				const res = await action()
				if (ok) toast(ok)
				return res
			} catch (e) {
				toast(e instanceof Error ? e.message : 'Ошибка', 'error')
				return undefined
			}
		},
		[toast],
	)

	useEffect(() => {
		Promise.all([reloadMe(), reloadStaff(), reloadBoards()]).catch((e: Error) => setError(e.message))
	}, [reloadMe, reloadStaff, reloadBoards])

	const value = useMemo(
		() => ({ me, staff, boards, error, reloadMe, reloadStaff, reloadBoards, toast, run, toasts }),
		[me, staff, boards, error, reloadMe, reloadStaff, reloadBoards, toast, run, toasts],
	)
	return <Ctx.Provider value={value}>{children}</Ctx.Provider>
}

export function useStore(): Store {
	const ctx = useContext(Ctx)
	if (!ctx) throw new Error('StoreProvider missing')
	return ctx
}

/** Загрузка данных с перезагрузкой по запросу. */
export function useLoad<T>(load: () => Promise<T>, deps: unknown[]): { data: T | null; reload: () => Promise<void>; loading: boolean } {
	const [data, setData] = useState<T | null>(null)
	const [loading, setLoading] = useState(true)
	const { toast } = useStore()
	const reload = useCallback(async () => {
		try {
			setData(await load())
		} catch (e) {
			toast(e instanceof Error ? e.message : 'Ошибка загрузки', 'error')
		} finally {
			setLoading(false)
		}
		// eslint-disable-next-line react-hooks/exhaustive-deps
	}, deps)
	useEffect(() => {
		setLoading(true)
		reload()
	}, [reload])
	return { data, reload, loading }
}
