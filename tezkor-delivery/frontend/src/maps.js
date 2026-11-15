export const tashkent = { lat: 41.311081, lng: 69.240562 }

export function coordinatePair(latitude, longitude) {
  if ([latitude, longitude].some((value) => value === null || value === undefined || typeof value === 'boolean' || typeof value === 'object' || String(value).trim() === '')) return null
  const lat = Number(latitude)
  const lng = Number(longitude)
  if (!Number.isFinite(lat) || !Number.isFinite(lng) || Math.abs(lat) > 90 || Math.abs(lng) > 180) return null
  return { lat: Number(lat.toFixed(6)), lng: Number(lng.toFixed(6)) }
}

export function openStreetMapUrl(destination, origin = null) {
  const point = coordinatePair(destination?.lat, destination?.lng)
  if (!point) return null
  const from = coordinatePair(origin?.lat, origin?.lng)
  if (from) {
    const query = new URLSearchParams({ engine: 'fossgis_osrm_car', route: `${from.lat},${from.lng};${point.lat},${point.lng}` })
    return `https://www.openstreetmap.org/directions?${query}`
  }
  return `https://www.openstreetmap.org/?mlat=${point.lat}&mlon=${point.lng}#map=17/${point.lat}/${point.lng}`
}
