import { useEffect, useRef, useState } from 'react'
import { Bell, CheckCircle2, ChevronLeft, ChevronRight, Clock3, LoaderCircle, RefreshCw, Send, TriangleAlert } from 'lucide-react'
import { api } from './api.js'

const statusLabels = { pending: 'Kutilmoqda', processing: 'Yuborilmoqda', sent: 'Yuborildi', failed: 'Xato' }
const dateTime = (value) => value ? new Date(value).toLocaleString('uz-UZ', { day: 'numeric', month: 'short', hour: '2-digit', minute: '2-digit' }) : '—'

export default function NotificationsPage({ onNotice }) {
  const [status, setStatus] = useState('')
  const [orderId, setOrderId] = useState('')
  const [page, setPage] = useState(1)
  const [revision, setRevision] = useState(0)
  const [data, setData] = useState({ results: [], count: 0, next: null, previous: null })
  const [summary, setSummary] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [retrying, setRetrying] = useState(null)
  const retryingRef = useRef(false)

  useEffect(() => {
    let cancelled = false
    setLoading(true)
    const load = async () => {
      if (document.hidden) return
      const query = new URLSearchParams({ page: String(page) })
      if (status) query.set('status', status)
      if (orderId) query.set('order_id', orderId.replace(/^0+(?=\d)/, ''))
      try {
        const [nextData, nextSummary] = await Promise.all([api(`/notifications/?${query}`), api('/notifications/summary/')])
        if (!cancelled) { setData(nextData); setSummary(nextSummary); setError('') }
      } catch (requestError) {
        if (!cancelled) {
          if (requestError.status === 404 && page > 1) setPage((current) => current - 1)
          else setError(requestError.message)
        }
      } finally { if (!cancelled) setLoading(false) }
    }
    load()
    const interval = setInterval(load, 15000)
    document.addEventListener('visibilitychange', load)
    return () => { cancelled = true; clearInterval(interval); document.removeEventListener('visibilitychange', load) }
  }, [page, status, orderId, revision])

  const retry = async (notificationId) => {
    if (retryingRef.current) return
    retryingRef.current = true
    setRetrying(notificationId)
    try {
      await api(`/notifications/${notificationId}/retry/`, { method: 'POST' })
      setPage(1)
      setRevision((current) => current + 1)
      onNotice('Xabarnoma qayta yuborish navbatiga qo‘shildi')
    } catch (requestError) { onNotice(requestError.message, 'error') }
    finally { retryingRef.current = false; setRetrying(null) }
  }

  return <>
    <div className="section-heading"><div><div className="eyebrow">MIJOZLAR BILAN ALOQA</div><h1>Telegram xabarlari</h1><p>Buyurtma holatlari haqida xabarlar va qayta yuborishlar.</p></div><button className="secondary-button" onClick={() => setRevision((current) => current + 1)} disabled={loading}><RefreshCw size={16} />Yangilash</button></div>
    <div className="stats-grid notification-stats">{[{ value: 'pending', icon: Clock3, color: 'orange' }, { value: 'processing', icon: Send, color: 'blue' }, { value: 'sent', icon: CheckCircle2, color: 'green' }, { value: 'failed', icon: TriangleAlert, color: 'purple' }].map(({ value, icon: Icon, color }) => <button className={`stat-card notification-stat ${status === value ? 'selected' : ''}`} key={value} onClick={() => { setStatus(status === value ? '' : value); setPage(1) }} aria-pressed={status === value}><span className={`stat-icon ${color}`}><Icon size={22} /></span><p>{statusLabels[value]}</p><strong>{summary?.counts[value] ?? '—'}</strong></button>)}</div>
    {summary && !summary.bot_configured && <div className="notification-banner"><TriangleAlert size={19} /><p>Telegram bot hali sozlanmagan. Xabarlar bazada saqlanadi; token sozlangach xato bilan tugagan so‘nggi xabarlarni qayta navbatga qo‘shing.</p></div>}
    {summary?.paused_until && <div className="notification-banner"><Clock3 size={19} /><p>Telegram yuborish limitiga yetildi. Avtomatik yuborish {dateTime(summary.paused_until)} dan keyin davom etadi.</p></div>}
    <div className="management-toolbar"><label>Holat<select value={status} onChange={(event) => { setStatus(event.target.value); setPage(1) }}><option value="">Barcha xabarlar</option>{Object.entries(statusLabels).map(([value, label]) => <option key={value} value={value}>{label}</option>)}</select></label><label>Buyurtma raqami<input inputMode="numeric" placeholder="Masalan, 12" value={orderId} onChange={(event) => { setOrderId(event.target.value.replace(/\D/g, '').slice(0, 19)); setPage(1) }} /></label>{(status || orderId) && <button className="text-button" onClick={() => { setStatus(''); setOrderId(''); setPage(1) }}>Filtrlarni tozalash</button>}</div>
    {error && <div className="notification-banner error" role="alert"><TriangleAlert size={19} /><p>{error}</p><button className="text-button" onClick={() => setRevision((current) => current + 1)}>Qayta urinish</button></div>}
    {loading ? <div className="notification-loading" role="status"><LoaderCircle size={25} className="spin" />Xabarlar yuklanmoqda…</div> : !error && <>
      <p className="results-count" role="status">{data.count} ta xabar · Har 15 soniyada yangilanadi</p>
      <div className="table-wrap"><table role="table" className="notification-table"><thead><tr><th>Buyurtma</th><th>Holat xabari</th><th>Yuborish</th><th>Urinishlar</th><th>Vaqt</th><th>Amal</th></tr></thead><tbody>{data.results.map((notification) => <tr role="row" key={notification.id}><td><strong>#{String(notification.order_id).padStart(4, '0')}</strong><small className="table-phone">{notification.customer_name}</small></td><td data-label="Holat xabari"><span>{notification.order_status_label}</span><details className="notification-text"><summary>Xabar matni</summary><p>{notification.text}</p></details></td><td data-label="Yuborish"><span className={`status-tag ${notification.status === 'sent' ? 'delivered' : notification.status === 'failed' ? 'cancelled' : notification.status}`}>{notification.status_label}</span>{notification.last_error && <p className="notification-error-text">{notification.last_error}</p>}</td><td data-label="Urinishlar">{notification.attempts} / {summary?.max_attempts || 5}</td><td data-label="Vaqt"><span>{dateTime(notification.sent_at || notification.created_at)}</span>{notification.status === 'pending' && notification.attempts > 0 && <small className="table-phone">Keyingi urinish: {dateTime(notification.next_attempt_at)}</small>}</td><td data-label="Amal">{notification.can_retry ? <button className="text-button" disabled={retrying !== null} onClick={() => retry(notification.id)}><RefreshCw size={14} />{retrying === notification.id ? 'Qo‘shilmoqda…' : 'Qayta yuborish'}</button> : <span className="muted">—</span>}</td></tr>)}</tbody></table>{!data.results.length && <div className="management-empty"><Bell size={31} /><p>Hozircha xabarnoma yo‘q.</p><p>Telegram orqali kirgan mijozning buyurtma xabarlari shu yerda ko‘rinadi.</p></div>}</div>
      <div className="notification-pagination"><span>{page}-sahifa · {Math.max(1, Math.ceil(data.count / 25))} sahifadan</span><div><button className="secondary-button" disabled={!data.previous} onClick={() => setPage((current) => current - 1)}><ChevronLeft size={16} />Oldingi</button><button className="secondary-button" disabled={!data.next} onClick={() => setPage((current) => current + 1)}>Keyingi<ChevronRight size={16} /></button></div></div>
    </>}
    <p className="form-hint management-hint">Xabarlar buyurtma holatlari ketma-ketligida yuboriladi. Avtomatik yuborish uchun xabarnoma xizmati ishlashi kerak. Buyurtmaning yangi holat xabari mavjud bo‘lsa, eski xato xabar qo‘lda qayta yuborilmaydi.</p>
  </>
}
