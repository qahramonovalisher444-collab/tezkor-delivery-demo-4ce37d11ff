import { useEffect, useRef, useState } from 'react'
import { ExternalLink, LocateFixed, MapPin, X } from 'lucide-react'
import L from 'leaflet'
import 'leaflet/dist/leaflet.css'
import { coordinatePair, openStreetMapUrl, tashkent } from './maps.js'

const pin = L.divIcon({ className: 'delivery-pin', html: '<span></span>', iconSize: [28, 36], iconAnchor: [14, 36] })

export default function LocationMap({ position, onChange, readOnly = false, disabled = false }) {
  const container = useRef(null)
  const map = useRef(null)
  const marker = useRef(null)
  const currentMarker = useRef(null)
  const callbacks = useRef({ onChange, disabled })
  const [locating, setLocating] = useState(false)
  const [error, setError] = useState('')
  const [tileError, setTileError] = useState(false)
  const [currentPosition, setCurrentPosition] = useState(null)
  const point = coordinatePair(position?.lat, position?.lng)
  callbacks.current = { onChange, disabled }

  useEffect(() => {
    let mounted = true
    const initial = coordinatePair(position?.lat, position?.lng)
    const instance = L.map(container.current, { center: initial || tashkent, zoom: initial ? 16 : 12, scrollWheelZoom: false })
    map.current = instance
    const tiles = L.tileLayer('https://tile.openstreetmap.org/{z}/{x}/{y}.png', {
      maxZoom: 19,
      attribution: '&copy; <a href="https://www.openstreetmap.org/copyright" target="_blank" rel="noopener">OpenStreetMap</a> contributors',
    }).addTo(instance)
    tiles.on('tileerror', () => { if (mounted) setTileError(true) })
    tiles.on('tileload', () => { if (mounted) setTileError(false) })
    if (!readOnly) instance.on('click', (event) => {
      if (!callbacks.current.disabled) {
        const value = event.latlng.wrap()
        callbacks.current.onChange?.(coordinatePair(value.lat, value.lng))
      }
    })
    const resize = new ResizeObserver(() => instance.invalidateSize({ pan: false }))
    resize.observe(container.current)
    return () => {
      mounted = false
      resize.disconnect()
      instance.remove()
      map.current = null
      marker.current = null
      currentMarker.current = null
    }
  }, [readOnly])

  useEffect(() => {
    const instance = map.current
    if (!instance) return
    if (!point) {
      marker.current?.remove()
      marker.current = null
      return
    }
    if (!marker.current) {
      marker.current = L.marker(point, { icon: pin, draggable: !readOnly && !disabled, keyboard: true, title: 'Yetkazish nuqtasi', alt: 'Yetkazish nuqtasi' }).addTo(instance)
      marker.current.on('dragend', () => {
        if (!callbacks.current.disabled) {
          const value = marker.current.getLatLng().wrap()
          callbacks.current.onChange?.(coordinatePair(value.lat, value.lng))
        }
      })
    } else marker.current.setLatLng(point)
    if (!readOnly && !disabled) marker.current.dragging?.enable()
    else marker.current.dragging?.disable()
    if (!instance.getBounds().contains(point)) instance.setView(point, Math.max(15, instance.getZoom()), { animate: false })
  }, [point?.lat, point?.lng, readOnly, disabled])

  const locate = () => {
    if (!navigator.geolocation) { setError('Qurilmada joylashuvni aniqlash mavjud emas.'); return }
    setError('')
    setLocating(true)
    navigator.geolocation.getCurrentPosition((result) => {
      setLocating(false)
      if (!map.current || callbacks.current.disabled) return
      const value = coordinatePair(result.coords.latitude, result.coords.longitude)
      if (!value) { setError('Joylashuvni aniqlab bo‘lmadi.'); return }
      if (readOnly) {
        setCurrentPosition(value)
        currentMarker.current?.remove()
        currentMarker.current = L.circleMarker(value, { radius: 7, color: '#fff', weight: 3, fillColor: '#397fe7', fillOpacity: 1 }).addTo(map.current)
        map.current.fitBounds(L.latLngBounds([value, point || value]), { padding: [28, 28], maxZoom: 16, animate: false })
      } else {
        callbacks.current.onChange?.(value)
        map.current.setView(value, 16, { animate: false })
      }
    }, (failure) => {
      setLocating(false)
      if (map.current) setError(failure.code === 1 ? 'Joylashuvga ruxsat berilmadi. Xaritadan foydalanishingiz mumkin.' : 'Joylashuv aniqlanmadi. Qayta urinib ko‘ring yoki xaritadan foydalaning.')
    }, { enableHighAccuracy: true, timeout: 12000, maximumAge: 30000 })
  }

  return <section className="location-map">
    <div className="map-toolbar"><div><MapPin size={17} /><strong>{readOnly ? 'Yetkazish nuqtasi' : 'Manzilni xaritada belgilang'}</strong></div><button type="button" className="text-button" disabled={disabled || locating} onClick={locate}><LocateFixed size={16} />{locating ? 'Aniqlanmoqda…' : 'Joylashuvim'}</button></div>
    <div ref={container} className="map-canvas" role="region" aria-label="Yetkazish nuqtasi xaritasi" />
    {!readOnly && <div className="map-selection"><button type="button" className="text-button" disabled={disabled} onClick={() => { const value = map.current.getCenter().wrap(); onChange(coordinatePair(value.lat, value.lng)) }}>Markazdagi nuqtani tanlash</button>{point && <button type="button" className="text-button danger" disabled={disabled} aria-label="Xarita nuqtasini olib tashlash" onClick={() => onChange(null)}><X size={14} />Tozalash</button>}</div>}
    <p className="map-coordinate" aria-live="polite">{point ? `${point.lat.toFixed(6)}, ${point.lng.toFixed(6)}` : 'Xaritaga bosing yoki joylashuvingizni aniqlang. Nuqta tanlash ixtiyoriy.'}</p>
    {tileError && <p className="map-error" role="status">Xarita rasmlari yuklanmadi. Internetni tekshiring; yozma manzil bilan davom etishingiz mumkin.</p>}
    {error && <p className="map-error" role="alert">{error}</p>}
    {readOnly && point && <a className="map-external" href={openStreetMapUrl(point, currentPosition)} target="_blank" rel="noopener noreferrer">{currentPosition ? 'OpenStreetMap’da yo‘nalishni ochish' : 'OpenStreetMap’da manzilni ochish'}<ExternalLink size={15} /></a>}
  </section>
}
