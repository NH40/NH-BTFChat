// Настройки доски (старшие): название и цвет, колонки (порядок, «готово», WIP-лимит), метки, удаление.
import { ArrowDown, ArrowUp, Plus, Trash2 } from 'lucide-react'
import { useState } from 'react'
import { api, type Board } from '../api'
import { useStore } from '../store'
import { confirmAction } from '../tg'
import { Field, Section, Sheet, Toggle } from '../ui'

const COLORS = ['#5b8cff', '#22c3a6', '#f5a524', '#c46bff', '#ff6b8b', '#4cc9f0', '#8bd450', '#ff8a4c']

export default function BoardSettingsSheet({ board, onClose, onDeleted }: { board: Board; onClose: () => void; onDeleted: () => void }) {
	const { me, run, reloadBoards } = useStore()
	const [name, setName] = useState(board.name)
	const [color, setColor] = useState(board.color)
	const [newColumn, setNewColumn] = useState('')
	const [newLabel, setNewLabel] = useState('')
	const [labelColor, setLabelColor] = useState(COLORS[1])

	const act = async (fn: () => Promise<unknown>, ok?: string) => {
		await run(fn, ok)
		await reloadBoards()
	}
	const move = (i: number, dir: -1 | 1) => {
		const ids = board.columns.map((c) => c.id)
		const j = i + dir
		if (j < 0 || j >= ids.length) return
		;[ids[i], ids[j]] = [ids[j], ids[i]]
		act(() => api.put(`/boards/${board.id}/columns/order`, { ids }))
	}

	return (
		<Sheet title='Настройки доски' onClose={onClose}>
			<div className='stack'>
				<Field label='Название'>
					<div className='row gap'>
						<input className='input' value={name} onChange={(e) => setName(e.target.value)} maxLength={128} />
						<button className='btn' disabled={!name.trim() || (name === board.name && color === board.color)} onClick={() => act(() => api.patch(`/boards/${board.id}`, { name, color }), 'Сохранено')}>
							OK
						</button>
					</div>
				</Field>
				<div className='row gap wrap'>
					{COLORS.map((c) => (
						<button key={c} type='button' className={`color-dot ${c === color ? 'on' : ''}`} style={{ background: c }} onClick={() => setColor(c)} aria-label={c} />
					))}
				</div>

				<Section title='Колонки'>
					{board.columns.map((c, i) => (
						<div key={c.id} className='list-row'>
							<input
								className='input'
								defaultValue={c.name}
								onBlur={(e) => e.target.value.trim() && e.target.value !== c.name && act(() => api.patch(`/columns/${c.id}`, { name: e.target.value }))}
							/>
							<input
								className='input narrow'
								type='number'
								min={0}
								placeholder='WIP'
								title='Лимит задач в работе'
								defaultValue={c.wip_limit ?? ''}
								onBlur={(e) => act(() => api.patch(`/columns/${c.id}`, { wip_limit: Number(e.target.value) || null }))}
							/>
							<button className='icon-btn' onClick={() => move(i, -1)} aria-label='Выше'>
								<ArrowUp size={15} />
							</button>
							<button className='icon-btn' onClick={() => move(i, 1)} aria-label='Ниже'>
								<ArrowDown size={15} />
							</button>
							<button
								className='icon-btn danger'
								aria-label='Удалить колонку'
								onClick={async () => (await confirmAction(`Удалить колонку «${c.name}»? Задачи переедут в первую открытую.`)) && act(() => api.del(`/columns/${c.id}`), 'Колонка удалена')}
							>
								<Trash2 size={15} />
							</button>
							<div className='full'>
								<Toggle checked={c.is_done} onChange={(v) => act(() => api.patch(`/columns/${c.id}`, { is_done: v }))} label='Перенос сюда = задача выполнена' />
							</div>
						</div>
					))}
					<div className='row gap'>
						<input className='input' placeholder='Новая колонка' value={newColumn} onChange={(e) => setNewColumn(e.target.value)} maxLength={64} />
						<button
							className='btn'
							disabled={!newColumn.trim()}
							onClick={() => act(() => api.post(`/boards/${board.id}/columns`, { name: newColumn.trim() })).then(() => setNewColumn(''))}
						>
							<Plus size={15} />
						</button>
					</div>
				</Section>

				<Section title='Метки'>
					<div className='row gap wrap'>
						{board.labels.map((l) => (
							<span key={l.id} className='label-dot big' style={{ background: l.color }}>
								{l.name}
								<button className='x' onClick={() => act(() => api.del(`/labels/${l.id}`))} aria-label='Удалить метку'>
									×
								</button>
							</span>
						))}
					</div>
					<div className='row gap'>
						<input className='input' placeholder='Новая метка' value={newLabel} onChange={(e) => setNewLabel(e.target.value)} maxLength={32} />
						<select className='input narrow' value={labelColor} onChange={(e) => setLabelColor(e.target.value)} style={{ color: labelColor }}>
							{COLORS.map((c) => (
								<option key={c} value={c} style={{ color: c }}>
									●
								</option>
							))}
						</select>
						<button
							className='btn'
							disabled={!newLabel.trim()}
							onClick={() => act(() => api.post(`/boards/${board.id}/labels`, { name: newLabel.trim(), color: labelColor })).then(() => setNewLabel(''))}
						>
							<Plus size={15} />
						</button>
					</div>
				</Section>

				<Section title='Обслуживание'>
					<button className='btn ghost' onClick={() => act(() => api.post(`/tasks/bulk-delete-done?board_id=${board.id}&older_days=30`), 'Старые выполненные — в архиве')}>
						В архив выполненные старше 30 дней
					</button>
					{me?.is_owner && (
						<button
							className='btn danger'
							onClick={async () => {
								if (!(await confirmAction(`Удалить доску «${board.name}» со всеми задачами? Это необратимо.`))) return
								await act(() => api.del(`/boards/${board.id}`), 'Доска удалена')
								onDeleted()
							}}
						>
							Удалить доску
						</button>
					)}
				</Section>
			</div>
		</Sheet>
	)
}
