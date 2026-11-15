import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { ArrowDown, ArrowRight, Bell, Bike, Check, CheckCircle2, ChevronDown, Clock3, Coffee, CreditCard, Flame, LayoutDashboard, LayoutGrid, Leaf, ListOrdered, LoaderCircle, LogIn, LogOut, MapPin, Minus, Package, Phone, Pizza, Plus, Search, ShieldCheck, ShoppingBag, Sparkles, Trash2, UserRound, Users, Utensils, X } from 'lucide-react'
import { api, session } from './api.js'
import ProfileForm from './ProfileForm.jsx'
import CheckoutForm from './CheckoutForm.jsx'
import CategoryManager from './CategoryManager.jsx'
import UserManagement from './UserManagement.jsx'
import OrderFilters from './OrderFilters.jsx'
import NotificationsPage from './NotificationsPage.jsx'
import OrderLocation from './OrderLocation.jsx'
import { filterOrders } from './orders.js'
import { configureTelegram, getTelegramInitData } from './telegram.js'
import { checkoutRequestId, clearCheckoutRequest, createCheckoutPayload, readCart, saveCart } from './storage.js'

const money = (value) => `${new Intl.NumberFormat('uz-UZ').format(Number(value))} so‘m`
const roles = { customer: 'Foydalanuvchi', courier: 'Kuryer', admin: 'Admin' }
const statusLabels = { pending: 'Yangi', confirmed: 'Tasdiqlangan', preparing: 'Tayyorlanmoqda', ready: 'Tayyor', delivering: 'Yo‘lda', delivered: 'Yetkazildi', cancelled: 'Bekor qilingan' }
const nextStatuses = { pending: 'confirmed', confirmed: 'preparing', preparing: 'ready', ready: 'delivering', delivering: 'delivered' }
const nextLabels = { confirmed: 'Tasdiqlash', preparing: 'Tayyorlashni boshlash', ready: 'Tayyor deb belgilash', delivering: 'Yetkazishni boshlash', delivered: 'Yetkazildi' }
const categoryIcons = { burger: Utensils, pizza: Pizza, drink: Coffee, salad: Leaf, snack: Flame, utensils: Utensils }
const dateTime = (value) => new Date(value).toLocaleString('uz-UZ', { day: 'numeric', month: 'short', hour: '2-digit', minute: '2-digit' })

function Empty({ icon: Icon = ShoppingBag, title, text }) {
  return <div className="empty"><span className="empty-icon"><Icon size={30} strokeWidth={1.5} /></span><h3>{title}</h3><p>{text}</p></div>
}

function Modal({ title, onClose, children }) {
  useEffect(() => {
    const previousOverflow = document.body.style.overflow
    document.body.style.overflow = 'hidden'
    const handleKey = (event) => { if (event.key === 'Escape') onClose() }
    document.addEventListener('keydown', handleKey)
    const previousFocus = document.activeElement
    const dialog = document.querySelector('[role="dialog"]')
    const focusable = () => [...dialog.querySelectorAll('button, input, select, textarea, [tabindex="0"]')].filter((element) => !element.disabled)
    focusable()[0]?.focus()
    const trapFocus = (event) => {
      if (event.key !== 'Tab') return
      const elements = focusable()
      const first = elements[0]
      const last = elements.at(-1)
      if (event.shiftKey && document.activeElement === first) { event.preventDefault(); last?.focus() }
      else if (!event.shiftKey && document.activeElement === last) { event.preventDefault(); first?.focus() }
    }
    dialog.addEventListener('keydown', trapFocus)
    return () => {
      document.body.style.overflow = previousOverflow
      document.removeEventListener('keydown', handleKey)
      dialog.removeEventListener('keydown', trapFocus)
      previousFocus?.focus()
    }
  }, [onClose])
  return <div className="modal-backdrop" onMouseDown={(event) => { if (event.target === event.currentTarget) onClose() }}><section className="modal" role="dialog" aria-modal="true" aria-labelledby="modal-title"><div className="modal-heading"><h2 id="modal-title">{title}</h2><button className="icon-button" aria-label="Yopish" onClick={onClose}><X size={21} /></button></div>{children}</section></div>
}

function ProductCard({ product, quantity, onAdd, onSubtract }) {
  return <article className="product-card"><div className="product-image-wrap"><img src={product.image_url || '/favicon.svg'} alt={product.name} loading="lazy" onError={(event) => { event.currentTarget.onerror = null; event.currentTarget.src = '/favicon.svg' }} />{product.badge && <span className="product-badge"><Flame size={12} />{product.badge}</span>}<span className="image-caption">{product.weight}</span></div><div className="product-content"><h3>{product.name}</h3><p>{product.description}</p><div className="product-footer"><strong>{money(product.price)}</strong>{quantity ? <div className="quantity-control"><button aria-label={`${product.name} sonini kamaytirish`} onClick={onSubtract}><Minus size={15} /></button><span>{quantity}</span><button aria-label={`${product.name} sonini oshirish`} disabled={quantity >= 30} onClick={onAdd}><Plus size={15} /></button></div> : <button className="add-button" aria-label={`${product.name} savatga qo‘shish`} onClick={onAdd}><Plus size={21} /></button>}</div></div></article>
}

function Cart({ cart, products, fee, onChange, onCheckout, onClose }) {
  const items = products.filter((product) => cart[product.id])
  const subtotal = items.reduce((total, product) => total + Number(product.price) * cart[product.id], 0)
  return <aside className="cart-panel"><div className="cart-heading"><div><ShoppingBag size={21} /><h2>Savatingiz</h2></div>{onClose ? <button className="icon-button" onClick={onClose} aria-label="Savatni yopish"><X size={20} /></button> : <span>{items.reduce((total, product) => total + cart[product.id], 0)}</span>}</div>{items.length ? <><div className="cart-items">{items.map((product) => <div className="cart-item" key={product.id}><img src={product.image_url || '/favicon.svg'} alt="" /><div><h4>{product.name}</h4><span>{money(product.price)}</span><div className="quantity-control"><button aria-label={`${product.name} kamaytirish`} onClick={() => onChange(product.id, -1)}><Minus size={13} /></button><span>{cart[product.id]}</span><button disabled={cart[product.id] >= 30} aria-label={`${product.name} oshirish`} onClick={() => onChange(product.id, 1)}><Plus size={13} /></button></div></div><button className="icon-button remove-item" aria-label={`${product.name} o‘chirish`} onClick={() => onChange(product.id, -cart[product.id])}><Trash2 size={15} /></button></div>)}</div><div className="cart-total"><p><span>Mahsulotlar</span><span>{money(subtotal)}</span></p><p><span>Yetkazib berish</span><span>{money(fee)}</span></p><div><strong>Jami</strong><strong>{money(subtotal + fee)}</strong></div></div><button className="primary-button checkout-button" onClick={onCheckout}>Buyurtma berish<ArrowRight size={18} /></button><p className="cart-note"><ShieldCheck size={13} />To‘lov yetkazilganda, naqd pulda</p></> : <Empty title="Hali hech narsa yo‘q" text="Yoqtirgan taomingizni qo‘shing. Mazali tanlov shu yerdan boshlanadi!" />}<div className="delivery-promise"><Bike size={27} /><div><strong>Issiq va o‘z vaqtida</strong><p>Har bir buyurtma — e’tibor bilan.</p></div></div></aside>
}

function OrderCard({ order, role, couriers, busy, onStatus, onAssign }) {
  const nextStatus = nextStatuses[order.status]
  const canAdvance = role === 'admin' ? Boolean(nextStatus) : role === 'courier' && ['ready', 'delivering'].includes(order.status)
  return <article className="order-card"><div className="order-top"><div><strong>Buyurtma #{String(order.id).padStart(4, '0')}</strong><p>{dateTime(order.created_at)}</p></div><span className={`status-tag ${order.status}`}>{statusLabels[order.status]}</span></div><div className="order-products">{order.items.map((item) => <p key={item.id}><span>{item.quantity} × {item.product_name}</span><strong>{money(Number(item.unit_price) * item.quantity)}</strong></p>)}</div><div className="order-info"><p><MapPin size={15} /><span>{order.address}</span></p><p><Phone size={15} /><a href={`tel:${order.phone}`}>{order.phone}</a><span className="muted">· {order.customer.name}</span></p>{order.note && <p className="order-note">{order.note}</p>}{order.courier && <p><Bike size={15} /><span>{order.courier.name}</span></p>}</div><OrderLocation order={order} /><div className="order-bottom"><div><small>Jami · naqd to‘lov</small><strong>{money(order.total)}</strong></div>{role === 'admin' && !['delivering', 'delivered', 'cancelled'].includes(order.status) && <select aria-label={`Buyurtma ${order.id} kuryeri`} value={order.courier?.id || ''} disabled={busy} onChange={(event) => onAssign(order.id, Number(event.target.value))}><option value="" disabled>Kuryer tayinlash</option>{couriers.map((courier) => <option key={courier.id} value={courier.id}>{courier.name}</option>)}</select>}</div>{(canAdvance || order.status === 'pending' && role === 'customer' || role === 'admin' && ['pending', 'confirmed', 'preparing', 'ready'].includes(order.status)) && <div className="order-actions">{canAdvance && <button className="primary-button small" disabled={busy || nextStatus === 'delivering' && !order.courier} onClick={() => onStatus(order.id, nextStatus)}>{nextLabels[nextStatus]}<ArrowRight size={15} /></button>}{(role === 'customer' && order.status === 'pending' || role === 'admin' && ['pending', 'confirmed', 'preparing', 'ready'].includes(order.status)) && <button className="text-button danger" disabled={busy} onClick={() => onStatus(order.id, 'cancelled')}>Bekor qilish</button>}</div>}<details className="order-history"><summary>Buyurtma tarixi <ChevronDown size={14} /></summary><div>{order.events.map((event) => <p key={event.id}><CheckCircle2 size={14} /><span>{statusLabels[event.status]}</span><time>{dateTime(event.created_at)}</time></p>)}</div></details></article>
}

function ProductEditor({ product, categories, onSave, onClose, busy }) {
  const [form, setForm] = useState(product || { name: '', description: '', price: '', category: categories[0]?.id || '', image_url: '', badge: '', weight: '', is_available: true })
  const setField = (field, value) => setForm((current) => ({ ...current, [field]: value }))
  return <Modal title={product ? 'Mahsulotni tahrirlash' : 'Yangi mahsulot'} onClose={onClose}><form onSubmit={(event) => { event.preventDefault(); onSave({ name: form.name, description: form.description, price: form.price, category: Number(form.category), image_url: form.image_url, badge: form.badge, weight: form.weight, is_available: form.is_available }, product?.id) }}><label>Mahsulot nomi<input required maxLength={120} value={form.name} onChange={(event) => setField('name', event.target.value)} /></label><div className="form-row"><label>Narxi (so‘m)<input type="number" required min="1" max="999999999999" step="1" value={form.price} onChange={(event) => setField('price', event.target.value)} /></label><label>Kategoriya<select required value={form.category} onChange={(event) => setField('category', event.target.value)}>{categories.map((category) => <option key={category.id} value={category.id}>{category.name}</option>)}</select></label></div><label>Tavsif<textarea maxLength={1000} value={form.description} onChange={(event) => setField('description', event.target.value)} /></label><label>Rasm manzili<input type="text" maxLength={600} value={form.image_url} onChange={(event) => setField('image_url', event.target.value)} /></label><div className="form-row"><label>Og‘irligi<input maxLength={40} placeholder="280 g" value={form.weight} onChange={(event) => setField('weight', event.target.value)} /></label><label>Belgi<input maxLength={30} placeholder="Bestseller" value={form.badge} onChange={(event) => setField('badge', event.target.value)} /></label></div><label className="checkbox-label"><input type="checkbox" checked={form.is_available} onChange={(event) => setField('is_available', event.target.checked)} />Sotuvda mavjud</label><button className="primary-button full" disabled={busy}>{busy ? 'Saqlanmoqda…' : 'Saqlash'}<Check size={18} /></button></form></Modal>
}

export default function App() {
  const [config, setConfig] = useState(null)
  const [user, setUser] = useState(null)
  const [products, setProducts] = useState([])
  const [categories, setCategories] = useState([])
  const [orders, setOrders] = useState([])
  const [users, setUsers] = useState([])
  const [stats, setStats] = useState(null)
  const [tab, setTab] = useState('menu')
  const [category, setCategory] = useState('all')
  const [search, setSearch] = useState('')
  const [orderFilters, setOrderFilters] = useState({ status: 'all', search: '', dateFrom: '', dateTo: '' })
  const [cart, setCart] = useState(readCart)
  const [modal, setModal] = useState(null)
  const [editingProduct, setEditingProduct] = useState(null)
  const [busy, setBusy] = useState(false)
  const busyRef = useRef(false)
  const [loading, setLoading] = useState(true)
  const [loadError, setLoadError] = useState('')
  const [notice, setNotice] = useState(null)
  const [checkout, setCheckout] = useState({ address: '', phone: '+998', note: '', save_details: true })
  const role = user?.role || 'customer'
  const closeModal = useCallback(() => setModal(null), [])
  const notify = useCallback((message, type = 'success') => setNotice({ message, type }), [])

  useEffect(() => { saveCart(cart) }, [cart])
  useEffect(() => {
    setCheckout({ address: user?.default_address || '', phone: user?.phone || '+998', note: '', save_details: true })
    setOrderFilters({ status: 'all', search: '', dateFrom: '', dateTo: '' })
  }, [user?.id])

  useEffect(() => {
    if (!notice) return
    const timeout = setTimeout(() => setNotice(null), 6000)
    return () => clearTimeout(timeout)
  }, [notice])

  const loadCatalog = useCallback(async () => {
    const [nextProducts, nextCategories] = await Promise.all([api('/products/'), api('/categories/')])
    setProducts(nextProducts)
    setCategories(nextCategories)
    setCart((current) => Object.fromEntries(Object.entries(current).filter(([productId]) => nextProducts.some((product) => product.id === Number(productId) && product.is_available))))
  }, [])

  const start = useCallback(async () => {
    setLoading(true)
    setLoadError('')
    try {
      configureTelegram()
      if (session.get()) {
        try { setUser(await api('/auth/me/')) } catch (error) { if (error.status !== 401) throw error; session.clear(); setUser(null) }
      }
      const initData = getTelegramInitData()
      if (!session.get() && initData) {
        const result = await api('/auth/telegram/', { method: 'POST', body: { init_data: initData } })
        session.set(result.token)
        setUser(result.user)
      }
      const [nextConfig] = await Promise.all([api('/config/'), loadCatalog()])
      setConfig(nextConfig)
    } catch (error) { setLoadError(error.message) }
    finally { setLoading(false) }
  }, [loadCatalog])

  useEffect(() => { start() }, [start])
  useEffect(() => {
    const script = document.getElementById('telegram-webapp-sdk')
    script?.addEventListener('load', configureTelegram)
    return () => script?.removeEventListener('load', configureTelegram)
  }, [])
  useEffect(() => {
    const expire = () => { setUser(null); setOrders([]); setUsers([]); setStats(null); setCheckout({ address: '', phone: '+998', note: '', save_details: true }); clearCheckoutRequest(); setTab('menu'); closeModal(); notify('Sessiya tugadi. Qayta kiring.', 'error') }
    window.addEventListener('session-expired', expire)
    return () => window.removeEventListener('session-expired', expire)
  }, [notify, closeModal])

  useEffect(() => {
    if (!user) return
    setTab(user.role === 'admin' ? 'dashboard' : user.role === 'courier' ? 'orders' : 'menu')
    loadCatalog().catch((error) => notify(error.message, 'error'))
    let cancelled = false
    const refresh = async () => {
      if (document.hidden) return
      try {
        const [nextOrders, nextUsers, nextStats] = await Promise.all([api('/orders/'), user.role === 'admin' ? api('/users/') : Promise.resolve([]), user.role === 'admin' ? api('/dashboard/') : Promise.resolve(null)])
        if (!cancelled) { setOrders(nextOrders); setUsers(nextUsers); setStats(nextStats) }
      } catch (error) { if (!cancelled) notify(error.message, 'error') }
    }
    refresh()
    const interval = setInterval(refresh, 15000)
    document.addEventListener('visibilitychange', refresh)
    return () => { cancelled = true; clearInterval(interval); document.removeEventListener('visibilitychange', refresh) }
  }, [user?.id, user?.role, loadCatalog, notify])

  const refreshWorkspace = async () => {
    const [nextOrders, nextUsers, nextStats] = await Promise.all([api('/orders/'), role === 'admin' ? api('/users/') : Promise.resolve([]), role === 'admin' ? api('/dashboard/') : Promise.resolve(null)])
    setOrders(nextOrders)
    setUsers(nextUsers)
    setStats(nextStats)
  }
  const runAction = async (action) => {
    if (busyRef.current) return false
    busyRef.current = true
    setBusy(true)
    try { await action(); return true } catch (error) { notify(error.message, 'error'); return false }
    finally { busyRef.current = false; setBusy(false) }
  }
  const demoLogin = (nextRole) => runAction(async () => {
    session.clear()
    clearCheckoutRequest()
    setUser(null); setOrders([]); setUsers([]); setStats(null); setTab('menu')
    const result = await api('/auth/demo/', { method: 'POST', body: { role: nextRole } })
    session.set(result.token)
    if (nextRole !== 'customer') setCart({})
    setUser(result.user)
    closeModal()
    notify(`${roles[nextRole]} sifatida kirdingiz`)
  })
  const changeCart = (productId, difference) => {
    if (!cart[productId] && difference > 0 && Object.keys(cart).length >= 50) { notify('Savatga ko‘pi bilan 50 xil mahsulot qo‘shish mumkin.', 'error'); return }
    setCart((current) => {
      const next = { ...current, [productId]: Math.max(0, Math.min(30, (current[productId] || 0) + difference)) }
      if (!next[productId]) delete next[productId]
      return next
    })
    window.Telegram?.WebApp?.HapticFeedback?.impactOccurred('light')
  }
  const openCheckout = () => {
    if (!user) { setModal('login'); return }
    setCheckout((current) => ({ ...current, address: current.address || user.default_address || '', phone: current.phone === '+998' ? user.phone || '+998' : current.phone }))
    setModal('checkout')
  }
  const submitOrder = (event) => {
    event.preventDefault()
    runAction(async () => {
      const payload = createCheckoutPayload(checkout, cart)
      const requestId = await checkoutRequestId(user.id, payload)
      const result = await api('/orders/', { method: 'POST', body: { ...payload, request_id: requestId } })
      clearCheckoutRequest()
      setCart({}); closeModal(); setTab('orders')
      setOrders((current) => [result, ...current.filter((order) => order.id !== result.id)])
      if (checkout.save_details) setUser((current) => ({ ...current, phone: result.phone, default_address: result.address }))
      notify(`Buyurtma #${result.id} qabul qilindi!`)
    })
  }
  const changeStatus = (orderId, nextStatus) => runAction(async () => {
    await api(`/orders/${orderId}/status/`, { method: 'POST', body: { status: nextStatus } })
    await refreshWorkspace()
    notify('Buyurtma holati yangilandi')
  })
  const assignCourier = (orderId, courier) => runAction(async () => {
    await api(`/orders/${orderId}/assign/`, { method: 'POST', body: { courier } })
    await refreshWorkspace()
    notify('Kuryer tayinlandi')
  })
  const saveProduct = (form, productId) => runAction(async () => {
    await api(productId ? `/products/${productId}/` : '/products/', { method: productId ? 'PATCH' : 'POST', body: form })
    await loadCatalog()
    closeModal()
    notify('Mahsulot saqlandi')
  })
  const saveProfile = (form) => runAction(async () => {
    const profile = await api('/auth/me/', { method: 'PATCH', body: form })
    setUser(profile)
    setCheckout((current) => ({ ...current, address: profile.default_address || '', phone: profile.phone || '+998', delivery_latitude: null, delivery_longitude: null }))
    notify('Profil ma’lumotlari saqlandi')
  })
  const saveCategory = (form, categoryId) => runAction(async () => {
    await api(categoryId ? `/categories/${categoryId}/` : '/categories/', { method: categoryId ? 'PATCH' : 'POST', body: form })
    await loadCatalog()
    notify('Kategoriya saqlandi')
  })
  const deleteCategory = (categoryId) => runAction(async () => {
    await api(`/categories/${categoryId}/`, { method: 'DELETE' })
    await loadCatalog()
    if (category === categoryId) setCategory('all')
    notify('Kategoriya o‘chirildi')
  })
  const changeUserRole = (userId, nextRole) => runAction(async () => {
    await api(`/users/${userId}/role/`, { method: 'POST', body: { role: nextRole } })
    await refreshWorkspace()
    notify('Foydalanuvchi roli yangilandi')
  })
  const changeUserActivity = (userId, isActive) => runAction(async () => {
    await api(`/users/${userId}/activity/`, { method: 'POST', body: { is_active: isActive } })
    await refreshWorkspace()
    notify(isActive ? 'Hisob faollashtirildi' : 'Hisob bloklandi va sessiyasi bekor qilindi')
  })
  const logout = () => runAction(async () => {
    await api('/auth/logout/', { method: 'POST' })
    session.clear(); setUser(null); setOrders([]); setUsers([]); setStats(null); setCart({}); setTab('menu')
    clearCheckoutRequest()
    await loadCatalog()
  })

  const visibleProducts = useMemo(() => products.filter((product) => product.is_available && (category === 'all' || product.category === category) && `${product.name} ${product.description}`.toLowerCase().includes(search.toLowerCase())), [products, category, search])
  const cartCount = Object.values(cart).reduce((total, quantity) => total + quantity, 0)
  const couriers = users.filter((person) => person.role === 'courier' && person.is_active)
  const visibleOrders = useMemo(() => filterOrders(orders, orderFilters), [orders, orderFilters])
  const navigation = role === 'admin' ? [{ id: 'dashboard', label: 'Umumiy ko‘rinish', icon: LayoutDashboard }, { id: 'orders', label: 'Buyurtmalar', icon: ListOrdered }, { id: 'products', label: 'Mahsulotlar', icon: Utensils }, { id: 'categories', label: 'Kategoriyalar', icon: LayoutGrid }, { id: 'users', label: 'Foydalanuvchilar', icon: Users }, { id: 'notifications', label: 'Xabarlar', icon: Bell }] : role === 'courier' ? [{ id: 'orders', label: 'Yetkazmalarim', icon: Bike }, { id: 'profile', label: 'Mening profilim', icon: UserRound }] : [{ id: 'menu', label: 'Menyu', icon: Utensils }, { id: 'orders', label: 'Buyurtmalarim', icon: ShoppingBag }, { id: 'profile', label: 'Mening profilim', icon: UserRound }]
  const cartProps = { cart, products, fee: config?.delivery_fee || 0, onChange: changeCart, onCheckout: openCheckout }

  return <div className="app-shell"><aside className="sidebar"><a className="brand" href="#" onClick={(event) => { event.preventDefault(); setTab(navigation[0].id) }}><span className="brand-mark"><Bike size={25} strokeWidth={2.5} /></span>tezkor<span className="brand-dot">.</span></a><span className="sidebar-label">{role === 'admin' ? 'BOSHQARUV PANELI' : role === 'courier' ? 'KURYER KABINETI' : 'MAZALI TANLOV'}</span><nav>{navigation.map(({ id, label, icon: Icon }) => <button key={id} className={tab === id ? 'nav-item active' : 'nav-item'} onClick={() => setTab(id)}><Icon size={19} />{label}{id === 'orders' && orders.some((order) => !['delivered', 'cancelled'].includes(order.status)) && <span className="nav-dot" />}</button>)}</nav><div className="sidebar-bottom"><div className="sidebar-promo"><span><Leaf size={22} /></span><h4>Yaxshi taom.<br />Yaxshi kayfiyat.</h4><p>Har kuni siz uchun<br />yangi va mazali.</p></div><div className="sidebar-footer"><span>Tezkor delivery</span><small>Sevgi bilan tayyorlanadi ♡</small></div></div></aside><div className="workspace"><header className="topbar"><div className="location"><span className="location-pin"><MapPin size={19} /></span><div><small>YETKAZIB BERISH HUDUDI</small><strong>Toshkent shahri</strong></div></div><div className="topbar-right">{config?.demo_auth && <button className="demo-pill" onClick={() => setModal('login')}><span />Demo · {roles[role]}<ChevronDown size={13} /></button>}<button className="profile-button" onClick={() => user ? setTab('profile') : setModal('login')}><span className="avatar">{user?.name?.[0] || <UserRound size={18} />}</span><span>{user?.name || 'Kirish'}<small>{user ? roles[role] : 'Xush kelibsiz'}</small></span></button></div></header><main>
    {loading ? <div className="loading-screen"><LoaderCircle className="spin" size={32} /><h3>Mazali tanlov tayyorlanmoqda…</h3></div> : loadError ? <div className="error-panel"><Package size={38} /><h2>Ulanishni tekshiramiz</h2><p>{loadError}</p><button className="primary-button" onClick={start}>Qayta urinish<ArrowRight size={17} /></button></div> : <>
      {tab === 'menu' && <div className="menu-layout"><div className="menu-main"><div className="page-intro"><div className="eyebrow"><span />YANGI TAYYORLANADI. TEZ YETKAZILADI.</div><h1>Bugun nima <span>yeymiz?</span></h1><p>Sevimli taomingiz bir necha bosish masofasida.</p></div><section className="hero-banner"><div className="hero-content"><span className="hero-tag"><Sparkles size={13} />Mazali tanlov, har kuni</span><h2>Katta ishtaha.<br /><span>Katta lazzat.</span></h2><p>Sersuv burgerlar, qaynoq pitsalar<br />va siz yoqtirgan barcha taomlar.</p><button onClick={() => document.getElementById('menu-catalog').scrollIntoView({ behavior: 'smooth', block: 'start' })}>Menyuni ko‘rish<ArrowDown size={15} /></button></div><div className="hero-art" aria-hidden="true"><div className="hero-orbit" /><img src="/menu/classic-burger.jpg" alt="" /><span className="hero-sticker"><Flame size={17} />Ishtaha ochar!</span><span className="hero-star">✳</span></div></section><div id="menu-catalog" className="catalog-heading"><h2>Bizning menyu <span>({visibleProducts.length})</span></h2><div className="search-box"><Search size={17} /><input aria-label="Taom izlash" placeholder="Taom izlash…" value={search} onChange={(event) => setSearch(event.target.value)} />{search && <button aria-label="Qidiruvni tozalash" onClick={() => setSearch('')}><X size={14} /></button>}</div></div><div className="categories"><button className={category === 'all' ? 'category active' : 'category'} onClick={() => setCategory('all')}><span><Utensils size={18} /></span>Barchasi</button>{categories.map((item) => { const Icon = categoryIcons[item.icon] || Utensils; return <button key={item.id} className={category === item.id ? 'category active' : 'category'} onClick={() => setCategory(item.id)}><span><Icon size={18} /></span>{item.name}</button> })}</div>{visibleProducts.length ? <div className="product-grid">{visibleProducts.map((product) => <ProductCard key={product.id} product={product} quantity={cart[product.id] || 0} onAdd={() => changeCart(product.id, 1)} onSubtract={() => changeCart(product.id, -1)} />)}</div> : <Empty icon={Search} title="Taom topilmadi" text="Boshqa nom yoki kategoriyani tanlab ko‘ring." />}<div className="menu-footnote"><ShieldCheck size={16} />Yangi mahsulotlar<em />Ehtiyotkor qadoqlash<em />Eshigingizgacha yetkazish</div></div><div className="desktop-cart"><Cart {...cartProps} /></div></div>}
      {tab === 'dashboard' && role === 'admin' && <><div className="section-heading"><div><div className="eyebrow">HAMMASI NAZORAT OSTIDA</div><h1>Salom, {user.name.split(' ')[0]} <span className="wave">✳</span></h1><p>Restoraningizning bugungi faoliyati.</p></div><span className="date-badge">{new Date().toLocaleDateString('uz-UZ', { day: 'numeric', month: 'long' })}</span></div><div className="stats-grid">{[{ label: 'Bugungi buyurtmalar', value: stats?.today_orders ?? '—', icon: ShoppingBag, color: 'orange' }, { label: 'Faol buyurtmalar', value: stats?.active_orders ?? '—', icon: Clock3, color: 'green' }, { label: 'Bugungi tushum', value: money(stats?.revenue || 0), icon: CreditCard, color: 'purple' }, { label: 'Faol kuryerlar', value: stats?.couriers ?? '—', icon: Bike, color: 'blue' }].map(({ label, value, icon: Icon, color }) => <div className="stat-card" key={label}><span className={`stat-icon ${color}`}><Icon size={22} /></span><p>{label}</p><strong>{value}</strong></div>)}</div><div className="catalog-heading"><h2>So‘nggi buyurtmalar</h2><button className="text-button" onClick={() => setTab('orders')}>Barchasi<ArrowRight size={16} /></button></div><div className="orders-grid">{orders.slice(0, 6).map((order) => <OrderCard key={order.id} {...{ order, role, couriers, busy }} onStatus={changeStatus} onAssign={assignCourier} />)}</div>{!orders.length && <Empty title="Birinchi buyurtmani kutyapmiz" text="Yangi buyurtmalar shu yerda ko‘rinadi." />}</>}
      {tab === 'orders' && <>
        <div className="section-heading"><div><div className="eyebrow">{role === 'courier' ? 'HAR BIR MANZIL MUHIM' : 'BUYURTMALAR HOLATI'}</div><h1>{role === 'courier' ? 'Yetkazmalarim' : role === 'admin' ? 'Buyurtmalar' : 'Buyurtmalarim'}</h1><p>{role === 'courier' ? 'Sizga tayinlangan buyurtmalar va manzillar.' : 'Har bir buyurtmaning holatini shu yerda kuzating.'}</p></div><span className="live-indicator"><span />Har 15 soniyada yangilanadi</span></div>
        {!user ? <div className="login-invitation"><Empty icon={LogIn} title="Avval hisobingizga kiring" text="Buyurtmalaringizni kuzatish uchun Telegram orqali kiring." /><button className="primary-button" onClick={() => setModal('login')}>Kirish<ArrowRight size={18} /></button></div> : <>
          <OrderFilters filters={orderFilters} onChange={setOrderFilters} count={visibleOrders.length} total={orders.length} />
          <div className="orders-grid">{visibleOrders.map((order) => <OrderCard key={order.id} {...{ order, role, couriers, busy }} onStatus={changeStatus} onAssign={assignCourier} />)}</div>
          {!visibleOrders.length && <Empty icon={Package} title={orders.length ? 'Mos buyurtma topilmadi' : 'Hozircha buyurtma yo‘q'} text={orders.length ? 'Qidiruv yoki sana filtrini o‘zgartirib ko‘ring.' : role === 'courier' ? 'Admin sizga buyurtma tayinlaganda shu yerda ko‘rinadi.' : 'Menyudan sevimli taomingizni tanlang.'} />}
        </>}
      </>}
      {tab === 'products' && role === 'admin' && <><div className="section-heading"><div><div className="eyebrow">MENYU BOSHQARUVI</div><h1>Mahsulotlar</h1><p>Taomlar, narxlar va ularning mavjudligi.</p></div><button className="primary-button" onClick={() => { setEditingProduct(null); setModal('product') }}><Plus size={18} />Mahsulot qo‘shish</button></div><div className="table-wrap"><table role="table"><thead><tr><th>Mahsulot</th><th>Kategoriya</th><th>Narx</th><th>Holat</th><th><span className="sr-only">Amal</span></th></tr></thead><tbody>{products.map((product) => <tr role="row" key={product.id}><td><div className="table-product"><img src={product.image_url || '/favicon.svg'} alt="" /><strong>{product.name}</strong></div></td><td data-label="Kategoriya">{product.category_name}</td><td data-label="Narx">{money(product.price)}</td><td data-label="Holat"><span className={`status-tag ${product.is_available ? 'delivered' : 'cancelled'}`}>{product.is_available ? 'Sotuvda' : 'Mavjud emas'}</span></td><td data-label="Amal"><button className="text-button" onClick={() => { setEditingProduct(product); setModal('product') }}>Tahrirlash</button></td></tr>)}</tbody></table></div></>}
      {tab === 'categories' && role === 'admin' && <CategoryManager categories={categories} busy={busy} onSave={saveCategory} onDelete={deleteCategory} />}
      {tab === 'users' && role === 'admin' && <UserManagement users={users} busy={busy} onRoleChange={changeUserRole} onActivityChange={changeUserActivity} />}
      {tab === 'notifications' && role === 'admin' && <NotificationsPage onNotice={notify} />}
      {tab === 'profile' && <>
        <div className="page-intro"><div className="eyebrow">SIZNING KABINETINGIZ</div><h1>Mening profilim</h1></div>
        {user ? <div className="profile-layout">
          <div className="profile-card"><span className="large-avatar">{user.name[0]}</span><h2>{user.name}</h2><span className="status-tag confirmed">{roles[role]}</span><div><p><span>Telegram ID</span><strong>{user.telegram_id || 'Demo hisob'}</strong></p><p><span>Telefon</span><strong>{user.phone || 'Buyurtmada ko‘rsatiladi'}</strong></p><p><span>Buyurtmalar</span><strong>{orders.length}</strong></p></div><button className="secondary-button" disabled={busy} onClick={logout}><LogOut size={17} />Hisobdan chiqish</button></div>
          <ProfileForm user={user} busy={busy} onSave={saveProfile} />
        </div> : <div className="login-invitation"><Empty icon={UserRound} title="Tezkor’ga xush kelibsiz" text="Telegram orqali kirib buyurtma bering va uning holatini kuzating." /><button className="primary-button" onClick={() => setModal('login')}>Hisobga kirish<ArrowRight size={18} /></button></div>}
      </>}
    </>}
    </main><footer className="page-footer"><span>© {new Date().getFullYear()} Tezkor</span><span>Mazali lahzalar, eshigingizgacha.</span></footer></div><nav className="mobile-nav">{navigation.map(({ id, label, icon: Icon }) => <button key={id} className={tab === id ? 'active' : ''} onClick={() => setTab(id)}><Icon size={21} /><span>{label}</span></button>)}{role === 'customer' && <button onClick={() => setModal('cart')} className="mobile-cart-button"><span><ShoppingBag size={21} />{cartCount > 0 && <b>{cartCount}</b>}</span><span>Savat</span></button>}</nav>
    {notice && <div className={`toast ${notice.type}`} role={notice.type === 'error' ? 'alert' : 'status'}>{notice.type === 'error' ? <X size={19} /> : <CheckCircle2 size={19} />}<span>{notice.message}</span><button aria-label="Xabarni yopish" onClick={() => setNotice(null)}><X size={16} /></button></div>}
    {modal === 'login' && <Modal title="Tezkor’ga xush kelibsiz" onClose={closeModal}><div className="login-body"><span className="login-icon"><Bike size={38} /></span><p>Buyurtma berish uchun Telegram botidagi <strong>«Menyuni ochish»</strong> tugmasidan foydalaning.</p>{config?.demo_auth && <><div className="demo-divider"><span>Mahalliy sinov uchun demo kirish</span></div><div className="demo-roles">{[{ value: 'customer', icon: UserRound, text: 'Taom tanlash va buyurtma berish' }, { value: 'courier', icon: Bike, text: 'Tayinlangan buyurtmalarni yetkazish' }, { value: 'admin', icon: ShieldCheck, text: 'Buyurtmalar, menyu va jamoa' }].map(({ value, icon: Icon, text }) => <button key={value} disabled={busy} onClick={() => demoLogin(value)}><Icon size={23} /><span><strong>{roles[value]}</strong><small>{text}</small></span><ArrowRight size={17} /></button>)}</div></>}</div></Modal>}
    {modal === 'cart' && <Modal title="Buyurtmangiz" onClose={closeModal}><Cart {...cartProps} /></Modal>}
    {modal === 'checkout' && <Modal title="Buyurtmani rasmiylashtirish" onClose={closeModal}><CheckoutForm checkout={checkout} setCheckout={setCheckout} deliveryFee={config.delivery_fee} total={products.reduce((total, product) => total + Number(product.price) * (cart[product.id] || 0), config.delivery_fee)} busy={busy} cartCount={cartCount} onSubmit={submitOrder} /></Modal>}
    {modal === 'product' && <ProductEditor product={editingProduct} categories={categories} onSave={saveProduct} onClose={closeModal} busy={busy} />}
  </div>
}
