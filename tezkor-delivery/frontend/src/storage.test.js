import assert from 'node:assert/strict'
import { beforeEach, test } from 'node:test'
import { checkoutRequestId, clearCheckoutRequest, createCheckoutPayload, readCart, sanitizeCart, saveCart } from './storage.js'

function memoryStorage() {
  const values = new Map()
  return {
    values,
    getItem: (key) => values.get(key) ?? null,
    setItem: (key, value) => values.set(key, value),
    removeItem: (key) => values.delete(key),
  }
}

beforeEach(() => clearCheckoutRequest(memoryStorage()))

test('cart survives a reload and only contains product ids and quantities', () => {
  const storage = memoryStorage()
  saveCart({ 1: 2, 7: 1 }, storage)
  assert.deepEqual(readCart(storage), { 1: 2, 7: 1 })
})

test('corrupted cart and invalid quantities cannot reach checkout', () => {
  const storage = memoryStorage()
  storage.setItem('tezkor-cart', '{invalid json')
  assert.deepEqual(readCart(storage), {})
  assert.deepEqual(sanitizeCart({ 1: 0, 2: -1, 3: 31, 4: '2', 5: 1.5, 6: 2, invalid: 1, '9007199254740992': 1 }), { 6: 2 })
  assert.deepEqual(sanitizeCart(null), {})
  assert.deepEqual(sanitizeCart([1, 2]), {})
  assert.equal(Object.keys(sanitizeCart(Object.fromEntries(Array.from({ length: 60 }, (_, index) => [index + 1, 1])))).length, 50)
})

test('blocked storage does not break cart or retries', async () => {
  const blocked = { getItem() { throw new Error('blocked') }, setItem() { throw new Error('blocked') }, removeItem() { throw new Error('blocked') } }
  saveCart({ 1: 2 }, blocked)
  assert.deepEqual(readCart(blocked), {})
  const first = await checkoutRequestId(1, { items: [{ product: 1, quantity: 2 }] }, blocked)
  assert.equal(await checkoutRequestId(1, { items: [{ product: 1, quantity: 2 }] }, blocked), first)
  clearCheckoutRequest(blocked)
})

test('same checkout retries reuse request id and do not store contact details', async () => {
  const storage = memoryStorage()
  const payload = { address: 'Toshkent, Navoiy 12', phone: '+998901234567', items: [{ product: 1, quantity: 1 }] }
  const first = await checkoutRequestId(1, payload, storage)
  assert.equal(await checkoutRequestId(1, payload, storage), first)
  const saved = storage.getItem('tezkor-checkout-request')
  assert.equal(saved.includes(payload.phone), false)
  assert.equal(saved.includes(payload.address), false)
  clearCheckoutRequest({ removeItem() {} })
  assert.equal(await checkoutRequestId(1, payload, storage), first)
})

test('changing checkout or customer gets a fresh request id', async () => {
  const storage = memoryStorage()
  const first = await checkoutRequestId(1, { address: 'First street' }, storage)
  const changed = await checkoutRequestId(1, { address: 'Second street' }, storage)
  assert.notEqual(first, changed)
  assert.notEqual(await checkoutRequestId(2, { address: 'Second street' }, storage), changed)
})

test('equivalent phone formatting and whitespace reuse the same checkout identity', async () => {
  const storage = memoryStorage()
  const first = createCheckoutPayload({ address: ' Toshkent, Navoiy 12 ', phone: '+998 (90) 123-45-67', note: '  ', save_details: true }, { 3: 2, 1: 1 })
  const second = createCheckoutPayload({ phone: '+998901234567', address: 'Toshkent, Navoiy 12', save_details: true, note: '' }, { 1: 1, 3: 2 })
  assert.deepEqual(first, second)
  assert.equal(await checkoutRequestId(1, first, storage), await checkoutRequestId(1, second, storage))
})

test('successful checkout clears retry identity for the next order', async () => {
  const storage = memoryStorage()
  const first = await checkoutRequestId(1, { items: [] }, storage)
  clearCheckoutRequest(storage)
  assert.equal(storage.getItem('tezkor-checkout-request'), null)
  assert.notEqual(await checkoutRequestId(1, { items: [] }, storage), first)
})
