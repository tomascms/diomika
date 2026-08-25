const fs = require('fs')
const { timedFetch } = require('./http.cjs')

async function probeHealth(cfg) {
  const api = cfg.apiUrl || 'https://api.diomika.com'
  const site = cfg.siteUrl || 'https://www.diomika.com'
  const out = {
    api: { ok: false, ms: null, version: null },
    db: { ok: false, ms: null },
    site: { ok: false, ms: null },
  }
  try {
    const r = await timedFetch(`${api}/health`)
    out.api.ok = r.ok && r.text.includes('online')
    out.api.ms = r.ms
    try {
      const j = JSON.parse(r.text)
      out.api.version = j.version || null
    } catch {
      /* ignore */
    }
  } catch {
    out.api.ok = false
  }
  try {
    const r = await timedFetch(`${api}/health/ready`)
    out.db.ok = r.ok
    out.db.ms = r.ms
  } catch {
    out.db.ok = false
  }
  try {
    const r = await timedFetch(site)
    out.site.ok = r.ok
    out.site.ms = r.ms
  } catch {
    out.site.ok = false
  }
  return out
}

function readLocalAlerts(logPath, limit = 40) {
  if (!fs.existsSync(logPath)) return []
  try {
    return fs
      .readFileSync(logPath, 'utf8')
      .trim()
      .split('\n')
      .filter(Boolean)
      .slice(-limit)
      .map((line) => {
        try {
          return JSON.parse(line)
        } catch {
          return { text: line, severity: 'info', title: line }
        }
      })
  } catch {
    return []
  }
}

async function fetchNtfyAlerts(cfg, limit = 20) {
  const url = cfg.ntfyTopicJsonUrl
  if (!url) return []
  try {
    const res = await fetch(url, { signal: AbortSignal.timeout(10000) })
    const rows = await res.json()
    return (Array.isArray(rows) ? rows : []).slice(-limit).map((row) => ({
      severity: row.tags?.includes('critical') ? 'critical' : 'warning',
      title: row.title || row.message || 'Alerta ntfy',
      message: row.message,
      ts: row.time ? row.time * 1000 : Date.now(),
      source: 'ntfy',
    }))
  } catch {
    return []
  }
}

module.exports = { probeHealth, readLocalAlerts, fetchNtfyAlerts }
