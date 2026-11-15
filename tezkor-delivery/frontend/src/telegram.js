export function getTelegramInitData(location = globalThis.location, webApp = globalThis.Telegram?.WebApp) {
  if (webApp?.initData) return webApp.initData
  const fragment = new URLSearchParams((location?.hash || '').replace(/^#/, ''))
  const query = new URLSearchParams(location?.search || '')
  return fragment.get('tgWebAppData') || query.get('tgWebAppData') || ''
}

export function configureTelegram() {
  const webApp = globalThis.Telegram?.WebApp
  webApp?.ready()
  webApp?.expand()
  webApp?.setHeaderColor('#f8f9f6')
  webApp?.setBackgroundColor('#f8f9f6')
}
