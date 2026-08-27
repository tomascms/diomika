const { getUserRoot } = require('./paths.cjs')
const path = require('path')
const fs = require('fs')

function storePath(app) {
  return path.join(getUserRoot(app), 'incident-history.json')
}

function loadIncidents(app) {
  const p = storePath(app)
  if (!fs.existsSync(p)) return { open: [], closed: [] }
  try {
    return JSON.parse(fs.readFileSync(p, 'utf8'))
  } catch {
    return { open: [], closed: [] }
  }
}

function saveIncidents(app, data) {
  fs.writeFileSync(storePath(app), JSON.stringify(data, null, 2), 'utf8')
}

function incidentKey(item) {
  return item.key || `${item.action || item.source}|${item.title || ''}`
}

function upsertOpen(app, item) {
  const data = loadIncidents(app)
  const key = incidentKey(item)
  const existing = data.open.find((i) => i.key === key)
  const now = Date.now()
  if (existing) {
    existing.lastSeen = now
    existing.detail = item.detail || existing.detail
    existing.severity = item.severity || existing.severity
  } else {
    data.open.unshift({
      key,
      action: item.action,
      severity: item.severity || 'warning',
      title: item.title,
      detail: item.detail || '',
      source: item.source || 'hub',
      file: item.file || null,
      url: item.url || null,
      openedAt: now,
      lastSeen: now,
      count: 1,
      status: 'open',
    })
  }
  data.open = data.open.slice(0, 80)
  saveIncidents(app, data)
  return data
}

function acknowledge(app, key) {
  const data = loadIncidents(app)
  const row = data.open.find((i) => i.key === key)
  if (row) {
    row.status = 'acked'
    row.ackedAt = Date.now()
  }
  saveIncidents(app, data)
  return data
}

function resolve(app, key) {
  const data = loadIncidents(app)
  const idx = data.open.findIndex((i) => i.key === key)
  if (idx >= 0) {
    const row = data.open.splice(idx, 1)[0]
    row.status = 'resolved'
    row.resolvedAt = Date.now()
    row.mttrMs = row.resolvedAt - (row.openedAt || row.resolvedAt)
    data.closed.unshift(row)
    data.closed = data.closed.slice(0, 200)
  }
  saveIncidents(app, data)
  return data
}

function syncFromRecommendations(app, recommendations) {
  const data = loadIncidents(app)
  const keys = new Set()
  for (const r of recommendations || []) {
    const item = {
      key: r.action || r.title,
      action: r.action,
      severity: r.severity,
      title: r.title,
      detail: r.detail,
      source: 'recommendation',
      file: r.file || null,
    }
    keys.add(item.key)
    upsertOpen(app, item)
  }
  // Auto-resolve open recs that disappeared
  const fresh = loadIncidents(app)
  const still = []
  for (const row of fresh.open) {
    if (row.source === 'recommendation' && row.action && !keys.has(row.key) && row.status !== 'acked') {
      row.status = 'resolved'
      row.resolvedAt = Date.now()
      row.mttrMs = row.resolvedAt - (row.openedAt || row.resolvedAt)
      fresh.closed.unshift(row)
    } else {
      still.push(row)
    }
  }
  fresh.open = still
  fresh.closed = fresh.closed.slice(0, 200)
  saveIncidents(app, fresh)
  return fresh
}

module.exports = {
  loadIncidents,
  saveIncidents,
  upsertOpen,
  acknowledge,
  resolve,
  syncFromRecommendations,
  incidentKey,
}
