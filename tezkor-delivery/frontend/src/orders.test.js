import assert from 'node:assert/strict'
import { test } from 'node:test'
import { filterOrders, restaurantDate } from './orders.js'

const orders = [
  { id: 1, status: 'ready', address: 'Toshkent, Bobur 45', phone: '+998901234567', customer: { name: 'Aziz Karimov' }, items: [{ product_name: 'Klassik burger' }], created_at: '2026-11-14T18:59:00Z' },
  { id: 2, status: 'delivered', address: 'Toshkent, Navoiy 12', phone: '+998911112233', customer: { name: 'Madina Aliyeva' }, items: [{ product_name: 'Pepperoni pitsa' }], created_at: '2026-11-14T19:01:00Z' },
  { id: 3, status: 'cancelled', address: 'Toshkent, Bobur 20', phone: '+998941112233', customer: { name: 'Madina Aliyeva' }, items: [{ product_name: 'Margarita pitsa' }], created_at: '2026-11-15T10:00:00Z' },
]

test('order search matches number, full name, formatted phone, address and food', () => {
  for (const search of ['#0001', 'aziz karimov', '+998 (90) 123-45-67', 'Bobur 45', 'BURGER']) {
    assert.deepEqual(filterOrders(orders, { search }).map((order) => order.id), [1])
  }
  assert.deepEqual(filterOrders(orders, { search: 'pitsa' }).map((order) => order.id), [2, 3])
  assert.deepEqual(filterOrders(orders, { search: 'not-found' }), [])
})

test('active and exact statuses exclude terminal orders', () => {
  assert.deepEqual(filterOrders(orders, { status: 'active' }).map((order) => order.id), [1])
  assert.deepEqual(filterOrders(orders, { status: 'delivered' }).map((order) => order.id), [2])
  assert.deepEqual(filterOrders(orders, { status: 'preparing' }), [])
})

test('date filtering follows Tashkent midnight independent of browser timezone', () => {
  assert.equal(restaurantDate(orders[0].created_at), '2026-11-14')
  assert.equal(restaurantDate(orders[1].created_at), '2026-11-15')
  assert.deepEqual(filterOrders(orders, { dateFrom: '2026-11-15', dateTo: '2026-11-15' }).map((order) => order.id), [2, 3])
  assert.deepEqual(filterOrders(orders, { dateTo: '2026-11-14' }).map((order) => order.id), [1])
})

test('search, status and date conditions combine without mutating the source', () => {
  assert.deepEqual(filterOrders(orders, { search: 'pitsa', status: 'delivered', dateFrom: '2026-11-15' }).map((order) => order.id), [2])
  assert.equal(orders.length, 3)
  assert.deepEqual(filterOrders(orders, { dateFrom: '2026-11-16', dateTo: '2026-11-14' }), [])
  assert.deepEqual(filterOrders(orders), orders)
})
