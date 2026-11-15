import assert from 'node:assert/strict'
import { test } from 'node:test'
import { getTelegramInitData } from './telegram.js'

test('Telegram startup data is available before the optional SDK finishes loading', () => {
  const data = 'auth_date=123&user=%7B%22id%22%3A123%7D&hash=signature'
  const hash = '#' + new URLSearchParams({ tgWebAppData: data, tgWebAppVersion: '8.0' })
  assert.equal(getTelegramInitData({ hash, search: '' }, null), data)
  assert.equal(getTelegramInitData({ hash: '', search: '?' + new URLSearchParams({ tgWebAppData: data }) }, null), data)
})

test('SDK data takes priority and ordinary browsers need no Telegram dependency', () => {
  assert.equal(getTelegramInitData({ hash: '#other=value', search: '' }, null), '')
  assert.equal(getTelegramInitData({ hash: '#tgWebAppData=old', search: '' }, { initData: 'verified-later-on-server' }), 'verified-later-on-server')
})
