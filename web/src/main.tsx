import { createRoot } from 'react-dom/client'
import { BrowserRouter } from 'react-router-dom'
import App from './App'
import { StoreProvider } from './store'
import './styles.css'
import { setupTelegram, startParam } from './tg'

setupTelegram()

// Диплинк на задачу: ?task=ID (кнопка «Открыть в BTF») или startapp=task_ID — превращаем в путь до первого рендера.
const params = new URLSearchParams(location.search)
const fromStart = startParam()?.match(/^task_(\d+)$/)?.[1]
const taskId = params.get('task') ?? fromStart
if (taskId && /^\d+$/.test(taskId)) history.replaceState(null, '', `/task/${taskId}`)

createRoot(document.getElementById('root')!).render(
	<BrowserRouter>
		<StoreProvider>
			<App />
		</StoreProvider>
	</BrowserRouter>,
)
