import assert from 'node:assert/strict'
import { test } from 'node:test'
import { coordinatePair, openStreetMapUrl } from './maps.js'
import { checkoutRequestId, clearCheckoutRequest, createCheckoutPayload } from './storage.js'

test('valid map points include zero and are normalized to six decimal places', () => {
  assert.deepEqual(coordinatePair('0', 0), { lat: 0, lng: 0 })
  assert.deepEqual(coordinatePair(41.31108123, '69.24056249'), { lat: 41.311081, lng: 69.240562 })
})

test('missing, nonnumeric and out of range coordinates cannot become a map point', () => {
  for (const point of [[null, 0], ['', 1], [true, 2], [undefined, 1], [91, 2], [1, 181], [NaN, 1], [1, Infinity], [[], 1]]) assert.equal(coordinatePair(...point), null)
})

test('map links use only validated OpenStreetMap coordinates', () => {
  const url = new URL(openStreetMapUrl({ lat: 41.3, lng: 69.2 }))
  assert.equal(url.origin, 'https://www.openstreetmap.org')
  assert.equal(url.searchParams.get('mlat'), '41.3')
  assert.equal(openStreetMapUrl({ lat: 'invalid', lng: 0 }), null)
})

test('route link contains current courier point and selected destination', () => {
  const url = new URL(openStreetMapUrl({ lat: 41.3, lng: 69.2 }, { lat: 41.31, lng: 69.22 }))
  assert.equal(url.pathname, '/directions')
  assert.equal(url.searchParams.get('route'), '41.31,69.22;41.3,69.2')
})

test('changing delivery point changes checkout retry identity', async () => {
  clearCheckoutRequest()
  const checkout = { address: 'Toshkent, Navoiy 12', phone: '+998901234567', note: '', delivery_latitude: 41.311081, delivery_longitude: 69.240562 }
  const first = createCheckoutPayload(checkout, { 1: 1 })
  assert.equal(first.delivery_latitude, '41.311081')
  const request = await checkoutRequestId(1, first)
  assert.equal(await checkoutRequestId(1, createCheckoutPayload({ ...checkout, delivery_longitude: '69.240562' }, { 1: 1 })), request)
  assert.notEqual(await checkoutRequestId(1, createCheckoutPayload({ ...checkout, delivery_longitude: 69.25 }, { 1: 1 })), request)
  assert.throws(() => createCheckoutPayload({ ...checkout, delivery_latitude: null }, { 1: 1 }))
  clearCheckoutRequest()
})
