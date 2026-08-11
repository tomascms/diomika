const prodBase = (import.meta.env.VITE_API_BASE_URL || '').replace(/\/+$/, '')

if (!import.meta.env.DEV && !prodBase) {
  throw new Error('VITE_API_BASE_URL em falta — configure antes do build de produção.')
}

const base = (import.meta.env.DEV ? '/api' : prodBase)

export const API_BASE_URL = base

const DEFAULT_TIMEOUT_MS = 25000

function requestHeaders(json = true) {
  const h = {}
  if (json) h['Content-Type'] = 'application/json'
  h['X-Request-Id'] = crypto.randomUUID()
  return h
}

export function parseApiDetail(body, status, requestId) {
  if (!body || typeof body !== 'object') {
    return requestId ? `Erro HTTP ${status} (ref: ${requestId.slice(0, 8)})` : `Erro HTTP ${status}`
  }
  const detail = body.detail ?? body.message
  if (typeof detail === 'string') {
    return requestId ? `${detail} (ref: ${requestId.slice(0, 8)})` : detail
  }
  if (Array.isArray(detail)) {
    const msg = detail.map((item) => item.msg || item.message || JSON.stringify(item)).join(' · ')
    return requestId ? `${msg} (ref: ${requestId.slice(0, 8)})` : msg
  }
  if (detail && typeof detail === 'object') {
    const msg = detail.msg || detail.message || JSON.stringify(detail)
    return requestId ? `${msg} (ref: ${requestId.slice(0, 8)})` : msg
  }
  return requestId ? `Erro HTTP ${status} (ref: ${requestId.slice(0, 8)})` : `Erro HTTP ${status}`
}

async function fetchWithTimeout(url, options = {}, timeoutMs = DEFAULT_TIMEOUT_MS) {
  const controller = new AbortController()
  const timer = setTimeout(() => controller.abort(), timeoutMs)
  try {
    return await fetch(url, { ...options, signal: controller.signal })
  } catch (err) {
    if (err.name === 'AbortError') {
      throw new Error('O servidor demorou demasiado a responder. Tente novamente.')
    }
    throw err
  } finally {
    clearTimeout(timer)
  }
}

export async function apiGet(path) {
  const headers = requestHeaders(false)
  const resp = await fetchWithTimeout(`${base}${path}`, { headers })
  const requestId = resp.headers.get('X-Request-Id') || headers['X-Request-Id']
  if (!resp.ok) {
    const err = await resp.json().catch(() => ({}))
    throw new Error(parseApiDetail(err, resp.status, requestId))
  }
  return resp.json()
}

export async function apiPost(path, body, options = {}) {
  const { apiKey = null, idempotencyKey = null, timeoutMs = DEFAULT_TIMEOUT_MS } = options
  const headers = requestHeaders(true)
  if (apiKey) headers['X-API-Key'] = apiKey
  if (idempotencyKey) headers['Idempotency-Key'] = idempotencyKey

  let resp
  try {
    resp = await fetchWithTimeout(`${base}${path}`, {
      method: 'POST',
      headers,
      body: JSON.stringify(body),
    }, timeoutMs)
  } catch (err) {
    if (err.message?.includes('demasiado')) throw err
    throw new Error('Não foi possível contactar o servidor. Verifique se a API está a correr.')
  }

  const requestId = resp.headers.get('X-Request-Id') || headers['X-Request-Id']
  if (!resp.ok) {
    const err = await resp.json().catch(() => ({}))
    throw new Error(parseApiDetail(err, resp.status, requestId))
  }
  return resp.json()
}
