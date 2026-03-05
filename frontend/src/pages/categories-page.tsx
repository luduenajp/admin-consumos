import { useEffect, useState } from 'react'
import {
    fetchCategories,
    createCategory,
    updateCategory,
    deleteCategory,
} from '../api/endpoints'
import type { Category, CategoryCreate } from '../api/types'

export function CategoriesPage() {
    const [categories, setCategories] = useState<Category[]>([])
    const [isLoading, setIsLoading] = useState(true)
    const [newCategory, setNewCategory] = useState<CategoryCreate>({ name: '', color: '#3b82f6' })
    const [editingId, setEditingId] = useState<number | null>(null)
    const [editForm, setEditForm] = useState<Partial<Category>>({})

    useEffect(() => {
        loadCategories()
    }, [])

    async function loadCategories() {
        setIsLoading(true)
        try {
            const data = await fetchCategories()
            setCategories(data)
        } finally {
            setIsLoading(false)
        }
    }

    async function handleCreate() {
        if (!newCategory.name.trim()) return
        await createCategory(newCategory)
        setNewCategory({ name: '', color: '#3b82f6' })
        await loadCategories()
    }

    async function handleDelete(id: number) {
        if (!confirm('¿Estás seguro? Las compras con esta categoría volverán a "Sin categoría"')) return
        await deleteCategory(id)
        await loadCategories()
    }

    async function handleUpdate(id: number) {
        if (!editForm.name?.trim()) return
        await updateCategory(id, { name: editForm.name, color: editForm.color })
        setEditingId(null)
        await loadCategories()
    }

    return (
        <div className="page">
            <div className="panel">
                <div className="panelTitle">Administrar Categorías</div>
                <p className="muted" style={{ marginBottom: '24px' }}>Crea y edita las categorías para clasificar tus gastos.</p>

                <div style={{ display: 'flex', gap: '12px', alignItems: 'flex-end', marginBottom: '32px' }}>
                    <div className="formRow" style={{ flex: 1, marginBottom: 0 }}>
                        <label className="label">Nueva Categoría</label>
                        <input
                            className="input"
                            placeholder="Ej: Supermercado"
                            type="text"
                            value={newCategory.name}
                            onChange={(e) => setNewCategory({ ...newCategory, name: e.target.value })}
                        />
                    </div>
                    <div className="formRow" style={{ marginBottom: 0 }}>
                        <label className="label">Color</label>
                        <input
                            className="input"
                            title="Color de categoría"
                            type="color"
                            value={newCategory.color || '#3b82f6'}
                            onChange={(e) => setNewCategory({ ...newCategory, color: e.target.value })}
                            style={{ width: '60px', padding: '4px', height: '44px', cursor: 'pointer' }}
                        />
                    </div>
                    <button className="button" onClick={handleCreate} disabled={!newCategory.name.trim()}>
                        Agregar
                    </button>
                </div>

                {isLoading ? (
                    <div style={{ padding: '40px', textAlign: 'center' }}>Cargando...</div>
                ) : (
                    <table className="table">
                        <thead>
                            <tr>
                                <th style={{ width: '80px' }}>Color</th>
                                <th>Nombre</th>
                                <th style={{ textAlign: 'right' }}>Acciones</th>
                            </tr>
                        </thead>
                        <tbody>
                            {categories.map((cat) => (
                                <tr key={cat.id}>
                                    <td>
                                        {editingId === cat.id ? (
                                            <input
                                                className="input"
                                                type="color"
                                                value={editForm.color || '#3b82f6'}
                                                onChange={(e) => setEditForm({ ...editForm, color: e.target.value })}
                                                style={{ width: '50px', padding: '2px', height: '32px' }}
                                            />
                                        ) : (
                                            <div
                                                style={{
                                                    width: '28px',
                                                    height: '28px',
                                                    borderRadius: '6px',
                                                    backgroundColor: cat.color || '#ccc',
                                                    boxShadow: 'inset 0 0 0 1px rgba(0,0,0,0.1)',
                                                }}
                                            />
                                        )}
                                    </td>
                                    <td style={{ fontWeight: 500 }}>
                                        {editingId === cat.id ? (
                                            <input
                                                className="input"
                                                type="text"
                                                value={editForm.name || ''}
                                                onChange={(e) => setEditForm({ ...editForm, name: e.target.value })}
                                                autoFocus
                                                style={{ padding: '4px 12px', width: '100%', maxWidth: '300px' }}
                                            />
                                        ) : (
                                            cat.name
                                        )}
                                    </td>
                                    <td style={{ textAlign: 'right' }}>
                                        {editingId === cat.id ? (
                                            <div style={{ display: 'flex', gap: '8px', justifyContent: 'flex-end' }}>
                                                <button className="button sm" onClick={() => handleUpdate(cat.id)}>Guardar</button>
                                                <button className="button sm ghost" onClick={() => setEditingId(null)}>Cancelar</button>
                                            </div>
                                        ) : (
                                            <div style={{ display: 'flex', gap: '8px', justifyContent: 'flex-end' }}>
                                                <button
                                                    className="button sm ghost"
                                                    onClick={() => {
                                                        setEditingId(cat.id)
                                                        setEditForm({ name: cat.name, color: cat.color })
                                                    }}
                                                >
                                                    Editar
                                                </button>
                                                <button className="button sm danger" onClick={() => handleDelete(cat.id)}>Eliminar</button>
                                            </div>
                                        )}
                                    </td>
                                </tr>
                            ))}
                            {categories.length === 0 && (
                                <tr>
                                    <td className="muted" colSpan={3} style={{ textAlign: 'center', padding: '40px' }}>
                                        No hay categorías definidas.
                                    </td>
                                </tr>
                            )}
                        </tbody>
                    </table>
                )}
            </div>
        </div>
    )
}
