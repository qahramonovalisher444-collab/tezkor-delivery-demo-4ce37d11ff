import { useState } from 'react'
import { ChevronDown, MapPin } from 'lucide-react'
import MapPanel from './MapPanel.jsx'
import { coordinatePair } from './maps.js'

export default function OrderLocation({ order }) {
  const [open, setOpen] = useState(false)
  const point = coordinatePair(order.delivery_latitude, order.delivery_longitude)
  if (!point) return null
  return <div className="order-location"><button type="button" className="text-button" aria-expanded={open} aria-controls={`order-map-${order.id}`} onClick={() => setOpen((current) => !current)}><MapPin size={16} />{open ? 'Xaritani yopish' : 'Xaritada ko‘rish'}<ChevronDown size={14} /></button>{open && <div id={`order-map-${order.id}`} className="order-location-map"><MapPanel position={point} readOnly /></div>}</div>
}
