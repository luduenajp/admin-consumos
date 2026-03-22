import { useEffect, useState } from 'react'
import { fetchGoals, createGoal, updateGoal, deleteGoal } from '../api/endpoints'
import type { FamilyGoal, FamilyGoalCreate, FamilyGoalUpdate } from '../api/types'
import { ConfirmDialog } from '../components/ConfirmDialog'

const PRIORITY_LABELS: Record<string, string> = {
    low: 'Baja',
    medium: 'Media',
    high: 'Alta',
}

const PRIORITY_COLORS: Record<string, string> = {
    low: '#7a6455',
    medium: '#c0693b',
    high: '#b91c1c',
}

function formatARS(amount: number | null | undefined): string {
    if (amount == null) return '—'
    return new Intl.NumberFormat('es-AR', { style: 'currency', currency: 'ARS', maximumFractionDigits: 0 }).format(amount)
}

export function GoalsPage() {
    const [goals, setGoals] = useState<FamilyGoal[]>([])
    const [isLoading, setIsLoading] = useState(true)
    const [newGoal, setNewGoal] = useState<FamilyGoalCreate>({
        title: '',
        description: null,
        target_amount: null,
        due_date: null,
        notes: null,
        priority: null,
    })
    const [editingId, setEditingId] = useState<number | null>(null)
    const [editForm, setEditForm] = useState<FamilyGoalUpdate>({})
    const [pendingDeleteId, setPendingDeleteId] = useState<number | null>(null)
    const [error, setError] = useState<string | null>(null)

    useEffect(() => {
        loadGoals()
    }, [])

    async function loadGoals() {
        setIsLoading(true)
        try {
            const data = await fetchGoals()
            setGoals(data)
        } finally {
            setIsLoading(false)
        }
    }

    async function handleCreate() {
        if (!newGoal.title.trim()) return
        setError(null)
        try {
            await createGoal({ ...newGoal, title: newGoal.title.trim() })
            setNewGoal({ title: '', description: null, target_amount: null, due_date: null, notes: null, priority: null })
            await loadGoals()
        } catch (e: unknown) {
            setError(e instanceof Error ? e.message : 'Error al crear el objetivo')
        }
    }

    async function handleUpdate(id: number) {
        if (editForm.title !== undefined && !editForm.title?.trim()) return
        setError(null)
        try {
            await updateGoal(id, editForm)
            setEditingId(null)
            setEditForm({})
            await loadGoals()
        } catch (e: unknown) {
            setError(e instanceof Error ? e.message : 'Error al actualizar')
        }
    }

    async function handleToggleComplete(goal: FamilyGoal) {
        await updateGoal(goal.id, { is_completed: !goal.is_completed })
        await loadGoals()
    }

    async function handleDelete(id: number) {
        await deleteGoal(id)
        await loadGoals()
    }

    function startEdit(goal: FamilyGoal) {
        setEditingId(goal.id)
        setEditForm({
            title: goal.title,
            description: goal.description,
            target_amount: goal.target_amount,
            due_date: goal.due_date,
            notes: goal.notes,
            priority: goal.priority,
        })
    }

    const pendingGoals = goals.filter(g => !g.is_completed)
    const completedGoals = goals.filter(g => g.is_completed)

    return (
        <>
        <div className="page">
            <h1 className="pageTitle">Objetivos Familiares</h1>

            {/* Create form */}
            <div className="panel" style={{ marginBottom: '24px' }}>
                <div className="panelTitle">Nuevo Objetivo</div>
                <p className="muted" style={{ marginBottom: '20px' }}>
                    Registrá metas familiares: vacaciones, remodelaciones, celebraciones, y más.
                </p>

                <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '12px' }}>
                    <div className="formRow" style={{ gridColumn: '1 / -1' }}>
                        <label className="label">Título *</label>
                        <input
                            className="input"
                            placeholder="Ej: Vacaciones en Bariloche"
                            type="text"
                            value={newGoal.title}
                            onChange={(e) => setNewGoal({ ...newGoal, title: e.target.value })}
                            onKeyDown={(e) => e.key === 'Enter' && handleCreate()}
                        />
                    </div>

                    <div className="formRow">
                        <label className="label">Presupuesto estimado (ARS)</label>
                        <input
                            className="input"
                            placeholder="Ej: 500000"
                            type="number"
                            min="0"
                            value={newGoal.target_amount ?? ''}
                            onChange={(e) => setNewGoal({ ...newGoal, target_amount: e.target.value ? parseFloat(e.target.value) : null })}
                        />
                    </div>

                    <div className="formRow">
                        <label className="label">Fecha objetivo</label>
                        <input
                            className="input"
                            type="month"
                            value={newGoal.due_date ?? ''}
                            onChange={(e) => setNewGoal({ ...newGoal, due_date: e.target.value || null })}
                        />
                    </div>

                    <div className="formRow">
                        <label className="label">Prioridad</label>
                        <select
                            className="input"
                            value={newGoal.priority ?? ''}
                            onChange={(e) => setNewGoal({ ...newGoal, priority: e.target.value || null })}
                        >
                            <option value="">Sin prioridad</option>
                            <option value="low">Baja</option>
                            <option value="medium">Media</option>
                            <option value="high">Alta</option>
                        </select>
                    </div>

                    <div className="formRow">
                        <label className="label">Notas</label>
                        <input
                            className="input"
                            placeholder="Notas adicionales..."
                            type="text"
                            value={newGoal.notes ?? ''}
                            onChange={(e) => setNewGoal({ ...newGoal, notes: e.target.value || null })}
                        />
                    </div>
                </div>

                {error && <div className="error" style={{ marginTop: '12px' }}>{error}</div>}

                <div style={{ marginTop: '16px' }}>
                    <button className="button" onClick={handleCreate} disabled={!newGoal.title.trim()}>
                        Agregar objetivo
                    </button>
                </div>
            </div>

            {/* Goals list */}
            {isLoading ? (
                <div style={{ padding: '40px', textAlign: 'center' }}>Cargando...</div>
            ) : (
                <>
                {/* Pending goals */}
                <div className="panel" style={{ marginBottom: '24px' }}>
                    <div className="panelTitle">Pendientes ({pendingGoals.length})</div>
                    <GoalTable
                        goals={pendingGoals}
                        editingId={editingId}
                        editForm={editForm}
                        onEditFormChange={setEditForm}
                        onStartEdit={startEdit}
                        onSaveEdit={handleUpdate}
                        onCancelEdit={() => { setEditingId(null); setEditForm({}) }}
                        onToggleComplete={handleToggleComplete}
                        onDelete={(id) => setPendingDeleteId(id)}
                        emptyText="No hay objetivos pendientes. ¡Agregá uno arriba!"
                    />
                </div>

                {/* Completed goals */}
                {completedGoals.length > 0 && (
                    <div className="panel">
                        <div className="panelTitle" style={{ color: 'var(--color-text-secondary)' }}>
                            Completados ({completedGoals.length})
                        </div>
                        <GoalTable
                            goals={completedGoals}
                            editingId={editingId}
                            editForm={editForm}
                            onEditFormChange={setEditForm}
                            onStartEdit={startEdit}
                            onSaveEdit={handleUpdate}
                            onCancelEdit={() => { setEditingId(null); setEditForm({}) }}
                            onToggleComplete={handleToggleComplete}
                            onDelete={(id) => setPendingDeleteId(id)}
                            emptyText=""
                            dimmed
                        />
                    </div>
                )}
                </>
            )}
        </div>

        <ConfirmDialog
            open={pendingDeleteId !== null}
            message="¿Eliminar este objetivo? Esta acción no se puede deshacer."
            confirmLabel="Eliminar"
            dangerous
            onConfirm={() => {
                if (pendingDeleteId !== null) handleDelete(pendingDeleteId)
                setPendingDeleteId(null)
            }}
            onCancel={() => setPendingDeleteId(null)}
        />
        </>
    )
}

interface GoalTableProps {
    goals: FamilyGoal[]
    editingId: number | null
    editForm: FamilyGoalUpdate
    onEditFormChange: (form: FamilyGoalUpdate) => void
    onStartEdit: (goal: FamilyGoal) => void
    onSaveEdit: (id: number) => void
    onCancelEdit: () => void
    onToggleComplete: (goal: FamilyGoal) => void
    onDelete: (id: number) => void
    emptyText: string
    dimmed?: boolean
}

function GoalTable({ goals, editingId, editForm, onEditFormChange, onStartEdit, onSaveEdit, onCancelEdit, onToggleComplete, onDelete, emptyText, dimmed }: GoalTableProps) {
    return (
        <table className="table">
            <thead>
                <tr>
                    <th style={{ width: '40px' }}></th>
                    <th>Objetivo</th>
                    <th style={{ width: '100px', textAlign: 'center' }}>Prioridad</th>
                    <th style={{ width: '160px', textAlign: 'right' }}>Presupuesto</th>
                    <th style={{ width: '110px', textAlign: 'center' }}>Fecha</th>
                    <th style={{ textAlign: 'right' }}>Acciones</th>
                </tr>
            </thead>
            <tbody>
                {goals.map((goal) => (
                    <tr key={goal.id} style={{ opacity: dimmed ? 0.6 : 1 }}>
                        <td style={{ textAlign: 'center' }}>
                            <input
                                type="checkbox"
                                checked={goal.is_completed}
                                onChange={() => onToggleComplete(goal)}
                                title={goal.is_completed ? 'Marcar como pendiente' : 'Marcar como completado'}
                                style={{ width: '18px', height: '18px', cursor: 'pointer', accentColor: 'var(--color-primary)' }}
                            />
                        </td>
                        <td>
                            {editingId === goal.id ? (
                                <div style={{ display: 'flex', flexDirection: 'column', gap: '6px' }}>
                                    <input
                                        className="input"
                                        type="text"
                                        value={editForm.title ?? ''}
                                        onChange={(e) => onEditFormChange({ ...editForm, title: e.target.value })}
                                        autoFocus
                                        style={{ padding: '4px 10px' }}
                                    />
                                    <input
                                        className="input"
                                        type="text"
                                        placeholder="Notas..."
                                        value={editForm.notes ?? ''}
                                        onChange={(e) => onEditFormChange({ ...editForm, notes: e.target.value || null })}
                                        style={{ padding: '4px 10px', fontSize: '13px' }}
                                    />
                                </div>
                            ) : (
                                <div>
                                    <span style={{ fontWeight: 500, textDecoration: goal.is_completed ? 'line-through' : 'none' }}>
                                        {goal.title}
                                    </span>
                                    {goal.notes && (
                                        <div className="muted" style={{ fontSize: '13px', marginTop: '2px' }}>{goal.notes}</div>
                                    )}
                                </div>
                            )}
                        </td>
                        <td style={{ textAlign: 'center' }}>
                            {editingId === goal.id ? (
                                <select
                                    className="input"
                                    value={editForm.priority ?? ''}
                                    onChange={(e) => onEditFormChange({ ...editForm, priority: e.target.value || null })}
                                    style={{ padding: '4px 8px', fontSize: '13px' }}
                                >
                                    <option value="">—</option>
                                    <option value="low">Baja</option>
                                    <option value="medium">Media</option>
                                    <option value="high">Alta</option>
                                </select>
                            ) : goal.priority ? (
                                <span style={{
                                    fontSize: '12px',
                                    fontWeight: 600,
                                    color: PRIORITY_COLORS[goal.priority] ?? 'inherit',
                                    textTransform: 'uppercase',
                                    letterSpacing: '0.05em',
                                }}>
                                    {PRIORITY_LABELS[goal.priority] ?? goal.priority}
                                </span>
                            ) : (
                                <span className="muted">—</span>
                            )}
                        </td>
                        <td style={{ textAlign: 'right', fontWeight: 500 }}>
                            {editingId === goal.id ? (
                                <input
                                    className="input"
                                    type="number"
                                    min="0"
                                    placeholder="0"
                                    value={editForm.target_amount ?? ''}
                                    onChange={(e) => onEditFormChange({ ...editForm, target_amount: e.target.value ? parseFloat(e.target.value) : null })}
                                    style={{ padding: '4px 10px', textAlign: 'right', width: '140px' }}
                                />
                            ) : (
                                formatARS(goal.target_amount)
                            )}
                        </td>
                        <td style={{ textAlign: 'center' }}>
                            {editingId === goal.id ? (
                                <input
                                    className="input"
                                    type="month"
                                    value={editForm.due_date ?? ''}
                                    onChange={(e) => onEditFormChange({ ...editForm, due_date: e.target.value || null })}
                                    style={{ padding: '4px 8px', fontSize: '13px' }}
                                />
                            ) : (
                                <span className={!goal.due_date ? 'muted' : ''}>
                                    {goal.due_date ? goal.due_date : '—'}
                                </span>
                            )}
                        </td>
                        <td style={{ textAlign: 'right' }}>
                            {editingId === goal.id ? (
                                <div style={{ display: 'flex', gap: '8px', justifyContent: 'flex-end' }}>
                                    <button className="button sm" onClick={() => onSaveEdit(goal.id)}>Guardar</button>
                                    <button className="button sm ghost" onClick={onCancelEdit}>Cancelar</button>
                                </div>
                            ) : (
                                <div style={{ display: 'flex', gap: '8px', justifyContent: 'flex-end' }}>
                                    <button className="button sm ghost" onClick={() => onStartEdit(goal)}>Editar</button>
                                    <button className="button sm danger" onClick={() => onDelete(goal.id)}>Eliminar</button>
                                </div>
                            )}
                        </td>
                    </tr>
                ))}
                {goals.length === 0 && emptyText && (
                    <tr>
                        <td className="muted" colSpan={6} style={{ textAlign: 'center', padding: '40px' }}>
                            {emptyText}
                        </td>
                    </tr>
                )}
            </tbody>
        </table>
    )
}
