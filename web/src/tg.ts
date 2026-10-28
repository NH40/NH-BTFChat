// Обёртка над Telegram.WebApp: initData, кнопка «Назад», вибрация, подтверждения.
interface TgWebApp {
	initData: string
	initDataUnsafe: { start_param?: string }
	ready(): void
	expand(): void
	setHeaderColor?(color: string): void
	setBackgroundColor?(color: string): void
	BackButton: { show(): void; hide(): void; onClick(cb: () => void): void; offClick(cb: () => void): void }
	HapticFeedback?: { impactOccurred(style: string): void; notificationOccurred(type: string): void }
	showConfirm?(message: string, cb: (ok: boolean) => void): void
	openTelegramLink?(url: string): void
	disableVerticalSwipes?(): void
}

const tg = (window as unknown as { Telegram?: { WebApp?: TgWebApp } }).Telegram?.WebApp

export function initData(): string {
	return tg?.initData ?? ''
}

export function insideTelegram(): boolean {
	return Boolean(tg?.initData)
}

export function setupTelegram(): void {
	if (!tg) return
	tg.ready()
	tg.expand()
	tg.setHeaderColor?.('#0f1218')
	tg.setBackgroundColor?.('#0f1218')
	tg.disableVerticalSwipes?.()
}

export function startParam(): string | undefined {
	return tg?.initDataUnsafe?.start_param
}

export function backButton(cb: (() => void) | null): () => void {
	if (!tg) return () => {}
	if (!cb) {
		tg.BackButton.hide()
		return () => {}
	}
	tg.BackButton.show()
	tg.BackButton.onClick(cb)
	return () => {
		tg.BackButton.offClick(cb)
		tg.BackButton.hide()
	}
}

export function haptic(kind: 'light' | 'success' | 'error' = 'light'): void {
	if (!tg?.HapticFeedback) return
	if (kind === 'light') tg.HapticFeedback.impactOccurred('light')
	else tg.HapticFeedback.notificationOccurred(kind)
}

export function confirmAction(message: string): Promise<boolean> {
	if (tg?.showConfirm) return new Promise((resolve) => tg.showConfirm!(message, resolve))
	return Promise.resolve(window.confirm(message))
}
