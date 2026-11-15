import { useEffect, useState } from 'react'
import { Check, MapPin, Phone, UserRound } from 'lucide-react'

export default function ProfileForm({ user, busy, onSave }) {
  const [form, setForm] = useState({ first_name: user.first_name || '', last_name: user.last_name || '', phone: user.phone || '', default_address: user.default_address || '' })
  useEffect(() => {
    setForm({ first_name: user.first_name || '', last_name: user.last_name || '', phone: user.phone || '', default_address: user.default_address || '' })
  }, [user.id, user.first_name, user.last_name, user.phone, user.default_address])
  const setField = (field, value) => setForm((current) => ({ ...current, [field]: value }))
  return <section className="profile-editor"><div className="profile-editor-heading"><span className="stat-icon green"><UserRound size={21} /></span><div><h2>Shaxsiy ma’lumotlar</h2><p>Keyingi buyurtmangiz uchun bir marta saqlang.</p></div></div><form onSubmit={(event) => { event.preventDefault(); onSave(form) }}><div className="form-row"><label>Ism<input autoComplete="given-name" maxLength={150} value={form.first_name} onChange={(event) => setField('first_name', event.target.value)} /></label><label>Familiya<input autoComplete="family-name" maxLength={150} value={form.last_name} onChange={(event) => setField('last_name', event.target.value)} /></label></div><label><span><Phone size={13} />Telefon raqam</span><input type="tel" autoComplete="tel" maxLength={24} placeholder="+998 90 123 45 67" value={form.phone} onChange={(event) => setField('phone', event.target.value)} /></label><label><span><MapPin size={13} />Yetkazish manzili</span><textarea autoComplete="street-address" maxLength={400} minLength={5} placeholder="Ko‘cha, uy, xonadon va mo‘ljal" value={form.default_address} onChange={(event) => setField('default_address', event.target.value)} /></label><p className="form-hint">Saqlangan telefon va manzil buyurtma berishda avtomatik to‘ldiriladi.</p><button className="primary-button" disabled={busy}>{busy ? 'Saqlanmoqda…' : 'Ma’lumotlarni saqlash'}<Check size={17} /></button></form></section>
}
