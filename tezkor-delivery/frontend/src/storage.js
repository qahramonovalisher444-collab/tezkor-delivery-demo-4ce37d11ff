import { coordinatePair } from './maps.js'

const cartKey = 'tezkor-cart'
const checkoutKey = 'tezkor-checkout-request'
let memoryRequest = null

export function sanitizeCart(value) {
  if (!value || typeof value !== 'object' || Array.isArray(value)) return {}
  return Object.fromEntries(Object.entries(value).filter(([product, quantity]) => /^[1-9]\d*$/.test(product) && Number.isSafeInteger(Number(product)) && Number.isInteger(quantity) && quantity >= 1 && quantity <= 30).slice(0, 50))
}

export function readCart(storage) {
  try { return sanitizeCart(JSON.parse((storage || globalThis.localStorage).getItem(cartKey) || '{}')) } catch { return {} }
}

export function saveCart(cart, storage) {
  try { (storage || globalThis.localStorage).setItem(cartKey, JSON.stringify(sanitizeCart(cart))) } catch { }
}

export function createCheckoutPayload(checkout, cart) {
  const payload = {
    address: checkout.address.trim(),
    phone: checkout.phone.replace(/[\s()\-]/g, ''),
    note: checkout.note.trim(),
    save_details: Boolean(checkout.save_details),
    items: Object.entries(sanitizeCart(cart)).map(([product, quantity]) => ({ product: Number(product), quantity })),
  }
  if (checkout.delivery_latitude != null || checkout.delivery_longitude != null) {
    const point = coordinatePair(checkout.delivery_latitude, checkout.delivery_longitude)
    if (!point) throw new Error('Xaritadagi nuqtani qaytadan tanlang.')
    payload.delivery_latitude = point.lat.toFixed(6)
    payload.delivery_longitude = point.lng.toFixed(6)
  }
  return payload
}

export async function checkoutRequestId(userId, payload, storage) {
  const encoded = new TextEncoder().encode(JSON.stringify({ userId, payload }))
  const digest = await globalThis.crypto.subtle.digest('SHA-256', encoded)
  const fingerprint = Array.from(new Uint8Array(digest), (byte) => byte.toString(16).padStart(2, '0')).join('')
  if (memoryRequest?.fingerprint === fingerprint) return memoryRequest.requestId
  let previous = memoryRequest
  try { previous = JSON.parse((storage || globalThis.sessionStorage).getItem(checkoutKey)) || previous } catch { }
  if (previous?.fingerprint === fingerprint && /^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i.test(previous.requestId)) return previous.requestId
  memoryRequest = { fingerprint, requestId: globalThis.crypto.randomUUID() }
  try { (storage || globalThis.sessionStorage).setItem(checkoutKey, JSON.stringify(memoryRequest)) } catch { }
  return memoryRequest.requestId
}

export function clearCheckoutRequest(storage) {
  memoryRequest = null
  try { (storage || globalThis.sessionStorage).removeItem(checkoutKey) } catch { }
}
