import { loadSettings } from './settings'

const TIMEOUT_MS = 30000
const WRITE_TIMEOUT_MS = 90000
const schemaCache = new Map()

function timeoutFor(method) {
  return ['POST', 'PUT', 'PATCH', 'DELETE'].includes(method) ? WRITE_TIMEOUT_MS : TIMEOUT_MS
}

function baseUrl() {
  return (loadSettings().apiBaseUrl || '').replace(/\/+$/, '')
}

function headers(json = true) {
  const h = {}
  if (json) h['Content-Type'] = 'application/json'
  const s = loadSettings()
  if (s.accessToken) {
    h.Authorization = `Bearer ${s.accessToken}`
  } else if (s.apiKey) {
    h['X-API-Key'] = s.apiKey
  }
  return h
}

function parseDetail(body, status) {
  if (!body || typeof body !== 'object') return `Erro HTTP ${status}`
  const detail = body.detail ?? body.message
  if (typeof detail === 'string') return detail
  if (Array.isArray(detail)) {
    return detail.map((i) => i.msg || i.message || JSON.stringify(i)).join(' · ')
  }
  return `Erro HTTP ${status}`
}

async function request(method, path, { body, params, headers: extraHeaders } = {}) {
  let url = `${baseUrl()}${path}`
  if (params) url += `?${new URLSearchParams(params)}`
  const controller = new AbortController()
  const timer = setTimeout(() => controller.abort(), timeoutFor(method))
  try {
    const resp = await fetch(url, {
      method,
      headers: { ...headers(body !== undefined), ...(extraHeaders || {}) },
      body: body !== undefined ? JSON.stringify(body) : undefined,
      signal: controller.signal,
    })
    if (!resp.ok) {
      const err = await resp.json().catch(() => ({}))
      throw new Error(parseDetail(err, resp.status))
    }
    const text = await resp.text()
    return text ? JSON.parse(text) : {}
  } finally {
    clearTimeout(timer)
  }
}

async function downloadBlob(path) {
  const resp = await fetch(`${baseUrl()}${path}`, { headers: headers(false) })
  if (!resp.ok) throw new Error(`Erro ao descarregar (${resp.status})`)
  return resp.blob()
}

async function uploadFile(table, field, file) {
  const url = `${baseUrl()}/admin/crud/upload-image?table=${encodeURIComponent(table)}&field=${encodeURIComponent(field)}`
  const fd = new FormData()
  fd.append('file', file)
  const controller = new AbortController()
  const timer = setTimeout(() => controller.abort(), timeoutFor('POST'))
  try {
    const resp = await fetch(url, { method: 'POST', headers: headers(false), body: fd, signal: controller.signal })
    if (!resp.ok) {
      const err = await resp.json().catch(() => ({}))
      throw new Error(parseDetail(err, resp.status))
    }
    return resp.json()
  } finally {
    clearTimeout(timer)
  }
}

export const api = {
  get: (path, params) => request('GET', path, { params }),
  post: (path, body) => request('POST', path, { body }),
  put: (path, body) => request('PUT', path, { body }),
  patch: (path, body) => request('PATCH', path, { body }),
  delete: (path, params) => request('DELETE', path, { params }),
  health: () => request('GET', '/health'),
  authStatus: () => request('GET', '/admin/auth/status'),
  login: (username, password, totp_code) =>
    request('POST', '/admin/auth/login', {
      body: totp_code ? { username, password, totp_code } : { username, password },
    }),
  mfaSetup: (username, password) =>
    request('POST', '/admin/auth/mfa/setup', { body: { username, password } }),
  mfaConfirm: (username, password, totp_code) =>
    request('POST', '/admin/auth/mfa/confirm', {
      body: { username, password, totp_code },
    }),
  logout: () => request('POST', '/admin/auth/logout'),
  me: () => request('GET', '/admin/auth/me'),
  workspace: () => request('GET', '/system/workspace'),
  formSchema: (table) => {
    if (schemaCache.has(table)) return schemaCache.get(table)
    const pending = request('GET', `/system/schema/form/${table}`).then((data) => {
      schemaCache.set(table, Promise.resolve(data))
      return data
    })
    schemaCache.set(table, pending)
    return pending
  },
  listRecords: async (table, params) => {
    const data = await request('GET', `/admin/crud/${table}`, { params })
    return Array.isArray(data) ? data : data?.items || []
  },
  listModelColors: async (colorsTable, modelId) => {
    if (!colorsTable || !modelId) return []
    const params = {
      id_modelo: modelId,
      visible_only: 'false',
      limit: '200',
    }
    const data = await request('GET', `/admin/crud/${colorsTable}`, { params })
    return Array.isArray(data) ? data : data?.items || []
  },
  publishRecord: (table, id) => request('POST', `/admin/crud/${table}/${id}/publish`),
  setVisibility: (table, id, visibilidade) =>
    request('PATCH', `/admin/crud/${table}/${id}/visibility`, { body: { visibilidade } }),
  setLida: (table, id, lida) =>
    request('PATCH', `/admin/crud/${table}/${id}/lida`, { body: { lida } }),
  getRecord: (table, id) => request('GET', `/admin/crud/${table}/${id}`),
  createRecord: (table, body, idempotencyKey = null) => {
    const opts = { body }
    if (idempotencyKey) {
      opts.headers = { 'Idempotency-Key': idempotencyKey }
    }
    return request('POST', `/admin/crud/${table}`, opts)
  },
  updateRecord: (table, id, body) => request('PUT', `/admin/crud/${table}/${id}`, { body }),
  deleteRecord: (table, id, hard = false) =>
    request('DELETE', `/admin/crud/${table}/${id}`, { params: { hard: String(hard) } }),
  uploadImage: (table, field, file) => uploadFile(table, field, file),
  createCategory: (body) => request('POST', '/system/categories/create', { body }),
  mergedList: async (viewKey, params = {}) => {
    const data = await request('GET', `/catalogo/admin/merged/${viewKey}`, {
      params: { limit: '500', offset: '0', ...params },
    })
    return Array.isArray(data) ? data : data?.items || []
  },
  schemaSync: (dryRun = false) => request('POST', `/system/schema/sync?dry_run=${dryRun}`),
  schemaStatus: () => request('GET', '/system/schema/status'),
  applyDeploySql: () => request('POST', '/system/apply-deploy-sql'),
  categoriesPlan: () => request('GET', '/system/categories/plan'),
  orderPicker: (categoryId) => request('GET', `/system/order-picker/${categoryId}`),
  createOrder: (body) => request('POST', '/encomendas-internas', { body }),
  orderPdf: (id) => downloadBlob(`/encomendas-internas/${id}/pdf`),
  orcamentoPdf: (id) => downloadBlob(`/orcamentos/${id}/pdf`),
  exportCsv: (table) => downloadBlob(`/admin/export/${table}`),
  importCsv: async (table, file, dryRun = false) => {
    const url = `${baseUrl()}/admin/import/${table}?dry_run=${dryRun}`
    const fd = new FormData()
    fd.append('file', file)
    const controller = new AbortController()
    const timer = setTimeout(() => controller.abort(), timeoutFor('POST'))
    try {
      const resp = await fetch(url, {
        method: 'POST',
        headers: headers(false),
        body: fd,
        signal: controller.signal,
      })
      if (!resp.ok) {
        const err = await resp.json().catch(() => ({}))
        throw new Error(parseDetail(err, resp.status))
      }
      return resp.json()
    } finally {
      clearTimeout(timer)
    }
  },
  listContact: async () => {
    const data = await request('GET', '/contacto', { params: { limit: '200', offset: '0' } })
    return Array.isArray(data) ? data : data?.items || []
  },
  getContactMessage: (id) => request('GET', `/contacto/${id}`),
  markContactRead: (id, lida = true) => request('PATCH', `/contacto/${id}/lida?lida=${lida}`),
  listCategories: () => request('GET', '/categorias'),
}
