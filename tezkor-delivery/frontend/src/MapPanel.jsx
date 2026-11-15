import { lazy, Suspense } from 'react'

const LocationMap = lazy(() => import('./LocationMap.jsx'))

export default function MapPanel(props) {
  return <Suspense fallback={<div className="map-loading" role="status">Xarita ochilmoqda…</div>}><LocationMap {...props} /></Suspense>
}
