import { useRef, useState } from 'react'
import { Check, Coffee, Flame, LayoutGrid, Leaf, Pencil, Pizza, Plus, Trash2, Utensils, X } from 'lucide-react'

const icons = { utensils: { label: 'Taom', icon: Utensils }, burger: { label: 'Burger', icon: Utensils }, pizza: { label: 'Pitsa', icon: Pizza }, snack: { label: 'Gazak', icon: Flame }, salad: { label: 'Salat', icon: Leaf }, drink: { label: 'Ichimlik', icon: Coffee } }
const emptyForm = { name: '', icon: 'utensils', position: 0 }

export default function CategoryManager({ categories, busy, onSave, onDelete }) {
  const [editingId, setEditingId] = useState(null)
  const [form, setForm] = useState(emptyForm)
  const [deleteId, setDeleteId] = useState(null)
  const nameInput = useRef(null)
  const reset = () => { setEditingId(null); setForm(emptyForm) }
  const edit = (category) => {
    setEditingId(category.id)
    setForm({ name: category.name, icon: category.icon, position: category.position })
    setDeleteId(null)
    nameInput.current?.focus()
  }
  const submit = async (event) => {
    event.preventDefault()
    if (await onSave({ ...form, position: Number(form.position) }, editingId)) reset()
  }
  const remove = async (categoryId) => {
    if (await onDelete(categoryId)) {
      setDeleteId(null)
      if (editingId === categoryId) reset()
    }
  }
  return <>
    <div className="section-heading"><div><div className="eyebrow">MENYUNI TARTIBGA SOLING</div><h1>Kategoriyalar</h1><p>Taom bo‘limlari, belgilar va menyudagi ko‘rinish tartibi.</p></div><span className="date-badge">{categories.length} ta kategoriya</span></div>
    <div className="category-management">
      <section className="management-panel"><div className="management-panel-heading"><LayoutGrid size={20} /><h2>Menyu bo‘limlari</h2></div>
        {!categories.length && <p className="management-empty">Birinchi kategoriya nomini kiriting va mahsulot qo‘shishni boshlang.</p>}
        <div className="category-list">{categories.map((category) => {
          const Icon = icons[category.icon]?.icon || Utensils
          return <article className={`category-row ${editingId === category.id ? 'selected' : ''}`} key={category.id}>
            <div className="category-row-main"><span className="category-row-icon"><Icon size={21} /></span><div><h3>{category.name}</h3><p>{category.product_count} ta mahsulot <span>·</span> Tartib: {category.position}</p></div><div className="category-row-actions"><button className="icon-button" aria-label={`${category.name} tahrirlash`} disabled={busy} onClick={() => edit(category)}><Pencil size={16} /></button><button className="icon-button danger" aria-label={`${category.name} o‘chirish`} title={category.product_count ? 'Avval mahsulotlarni boshqa kategoriyaga o‘tkazing' : 'Kategoriyani o‘chirish'} disabled={busy || category.product_count > 0} onClick={() => setDeleteId(category.id)}><Trash2 size={16} /></button></div></div>
            {deleteId === category.id && <div className="inline-confirm" role="alert"><p>«{category.name}» kategoriyasi o‘chirilsinmi?</p><button className="text-button danger" disabled={busy} onClick={() => remove(category.id)}>Ha, o‘chirish</button><button className="text-button" disabled={busy} onClick={() => setDeleteId(null)}>Qaytish</button></div>}
          </article>
        })}</div><p className="form-hint category-note">Mahsuloti bor kategoriyani o‘chirish uchun avval mahsulotlarni boshqa bo‘limga ko‘chiring.</p>
      </section>
      <section className="management-panel category-form-panel"><div className="management-panel-heading">{editingId ? <Pencil size={19} /> : <Plus size={20} />}<h2>{editingId ? 'Kategoriyani tahrirlash' : 'Yangi kategoriya'}</h2>{editingId && <button className="icon-button" disabled={busy} aria-label="Tahrirlashni bekor qilish" onClick={reset}><X size={17} /></button>}</div>
        <form onSubmit={submit}><fieldset disabled={busy}><label>Kategoriya nomi<input ref={nameInput} required maxLength={80} placeholder="Masalan, Shirinliklar" value={form.name} onChange={(event) => setForm((current) => ({ ...current, name: event.target.value }))} /></label><div className="form-row"><label>Belgi<select value={form.icon} onChange={(event) => setForm((current) => ({ ...current, icon: event.target.value }))}>{Object.entries(icons).map(([value, option]) => <option key={value} value={value}>{option.label}</option>)}</select></label><label>Menyudagi tartib<input type="number" required min={0} max={10000} step={1} value={form.position} onChange={(event) => setForm((current) => ({ ...current, position: event.target.value }))} /></label></div><p className="form-hint">Tartib soni kichik bo‘lgan kategoriya menyuda oldinroq chiqadi.</p><button className="primary-button full" type="submit">{busy ? 'Saqlanmoqda…' : editingId ? 'O‘zgarishlarni saqlash' : 'Kategoriya qo‘shish'}<Check size={17} /></button></fieldset></form>
      </section>
    </div>
  </>
}
