/** Backoffice local — sessão utilizador (Bearer) + fallback API key máquina. */
const STORAGE_KEY = 'diomika-backoffice-settings'
const SESSION_TOKEN_KEY = 'diomika-backoffice-session-token'
const SESSION_USER_KEY = 'diomika-backoffice-session-user'
const LEGACY_API_KEY = 'diomika-backoffice-session'

const DEV_API_KEY =
  typeof __DIOMIKA_DEV_API_KEY__ !== 'undefined' ? __DIOMIKA_DEV_API_KEY__ : ''

/** Sempre o proxy same-origin do Electron/Vite — nunca a API pública da loja. */
const LOCAL_API_BASE = '/api'

function readStorage() {
  try {
    const raw = localStorage.getItem(STORAGE_KEY)
    return raw ? JSON.parse(raw) : {}
  } catch {
    return {}
  }
}

export function readSessionToken() {
  try {
    return sessionStorage.getItem(SESSION_TOKEN_KEY) || ''
  } catch {
    return ''
  }
}

export function writeSessionToken(token) {
  try {
    if (token) sessionStorage.setItem(SESSION_TOKEN_KEY, token)
    else sessionStorage.removeItem(SESSION_TOKEN_KEY)
  } catch {
    /* ignore */
  }
}

export function readSessionUser() {
  try {
    const raw = sessionStorage.getItem(SESSION_USER_KEY)
    return raw ? JSON.parse(raw) : null
  } catch {
    return null
  }
}

export function writeSessionUser(user) {
  try {
    if (user) sessionStorage.setItem(SESSION_USER_KEY, JSON.stringify(user))
    else sessionStorage.removeItem(SESSION_USER_KEY)
  } catch {
    /* ignore */
  }
}

function readLegacyApiKey() {
  try {
    return sessionStorage.getItem(LEGACY_API_KEY) || ''
  } catch {
    return ''
  }
}

export function defaultSettings() {
  return {
    apiBaseUrl: LOCAL_API_BASE,
    apiKey: '',
    accessToken: '',
  }
}

export function isRemoteApiUrl(url) {
  const u = (url || '').trim().toLowerCase()
  if (!u || u.startsWith('/api')) return false
  return !u.includes('127.0.0.1') && !u.includes('localhost')
}

export function loadSettings() {
  try {
    const saved = readStorage()
    const defaults = defaultSettings()
    const token = readSessionToken()
    const legacyKey = readLegacyApiKey()
    // Ignora apiBaseUrl gravado antigo (ex.: https://api.diomika.com ou :8000)
    return {
      ...defaults,
      ...saved,
      accessToken: token || '',
      apiKey: token ? '' : (legacyKey || saved.apiKey || (import.meta.env.DEV ? DEV_API_KEY : '') || ''),
      apiBaseUrl: LOCAL_API_BASE,
    }
  } catch {
    return defaultSettings()
  }
}

export function saveSettings(partial) {
  const current = loadSettings()
  const next = { ...current, ...partial, apiBaseUrl: LOCAL_API_BASE }
  if ('accessToken' in partial) {
    writeSessionToken(partial.accessToken || '')
  }
  if ('apiKey' in partial && !partial.accessToken) {
    try {
      if (partial.apiKey) sessionStorage.setItem(LEGACY_API_KEY, partial.apiKey)
      else sessionStorage.removeItem(LEGACY_API_KEY)
    } catch {
      /* ignore */
    }
  }
  localStorage.setItem(STORAGE_KEY, JSON.stringify({ apiBaseUrl: LOCAL_API_BASE }))
  return loadSettings()
}

export function clearSession() {
  writeSessionToken('')
  writeSessionUser(null)
  try {
    sessionStorage.removeItem(LEGACY_API_KEY)
  } catch {
    /* ignore */
  }
}

export function clearSettings() {
  localStorage.removeItem(STORAGE_KEY)
  clearSession()
  return defaultSettings()
}

export function isAuthenticated() {
  const s = loadSettings()
  return Boolean(s.accessToken?.trim() || s.apiKey?.trim())
}

/** Sempre configurado em local — proxy /api. Auth é sessão ou API key. */
export function isConfigured() {
  return true
}

export function bootstrapSettings() {
  return saveSettings({ apiBaseUrl: LOCAL_API_BASE })
}

export function mapApiError(message) {
  const msg = String(message || '')
  if (status401(msg)) return 'Sessão expirada ou credenciais inválidas. Volte a iniciar sessão.'
  if (/403|localhost na produção|Admin\/system/i.test(msg)) {
    return 'Acesso admin bloqueado. Use o Backoffice local (EXE/atalho) com a API em 127.0.0.1:8001 — não pela internet.'
  }
  if (/502|inacessível|API local/i.test(msg)) {
    return 'API local offline. Feche e abra de novo pelo atalho Diomika Backoffice (arranca a API automaticamente).'
  }
  if (/abort|timeout/i.test(msg)) return 'API inacessível. Confirme que está a correr em http://127.0.0.1:8001'
  if (/fetch|network|failed/i.test(msg)) {
    return 'Não foi possível contactar a API local. Abra pelo atalho Diomika Backoffice (não pelo EXE isolado sem API).'
  }
  if (/500|internal|Erro HTTP 500/i.test(msg)) return 'Erro no servidor. Verifique os logs da API ou tente Schema & Sync.'
  return msg || 'Erro de ligação.'
}

function status401(msg) {
  return msg.includes('401') || /sessão/i.test(msg) || /api key/i.test(msg) || /inválida/i.test(msg)
}
