const baseUrl = (import.meta.env.VITE_API_URL || '/api').replace(/\/$/, '')
const tokenKey = 'tezkor-token'
let memoryToken = null

export const session = {
  get: () => {
    try { return sessionStorage.getItem(tokenKey) || memoryToken } catch { return memoryToken }
  },
  set: (token) => {
    memoryToken = token
    try { sessionStorage.setItem(tokenKey, token) } catch { }
  },
  clear: () => {
    memoryToken = null
    try { sessionStorage.removeItem(tokenKey) } catch { }
  },
}

function errorText(value) {
  if (typeof value === 'string') return value
  if (Array.isArray(value)) return value.map(errorText).join(' ')
  if (value && typeof value === 'object') return Object.entries(value).map(([key, detail]) => `${key === 'detail' || key === 'non_field_errors' ? '' : `${key}: `}${errorText(detail)}`).join(' ')
  return 'So‘rovni bajarib bo‘lmadi.'
}

export async function api(path, options = {}) {
  const controller = new AbortController()
  const timeout = setTimeout(() => controller.abort(), 20000)
  try {
    const token = session.get()
    const response = await fetch(`${baseUrl}${path}`, {
      ...options,
      headers: { 'Content-Type': 'application/json', ...(token ? { Authorization: `Token ${token}` } : {}), ...options.headers },
      signal: controller.signal,
      body: options.body ? JSON.stringify(options.body) : undefined,
    })
    const result = response.status === 204 ? null : await response.json()
    if (!response.ok) {
      if (response.status === 401 && token) {
        session.clear()
        window.dispatchEvent(new Event('session-expired'))
      }
      const error = new Error(errorText(result))
      error.status = response.status
      throw error
    }
    return result
  } catch (error) {
    if (error.name === 'AbortError') throw new Error('Server javobi kechikdi. Qayta urinib ko‘ring.')
    if (error instanceof TypeError) throw new Error('Serverga ulanib bo‘lmadi. Backend ishlayotganini tekshiring.')
    throw error
  } finally {
    clearTimeout(timeout)
  }
}
