const fs = require('fs')
const path = require('path')
const { getUserRoot } = require('./paths.cjs')

const FILE = 'hub-dismissed.json'

function storePath(app) {
  return path.join(getUserRoot(app), FILE)
}

function loadDismissed(app) {
  const p = storePath(app)
  if (!fs.existsSync(p)) return { alerts: [], recommendations: [], sentry: [], ci: [] }
  try {
    const data = JSON.parse(fs.readFileSync(p, 'utf8'))
    return {
      alerts: Array.isArray(data.alerts) ? data.alerts : [],
      recommendations: Array.isArray(data.recommendations) ? data.recommendations : [],
      sentry: Array.isArray(data.sentry) ? data.sentry : [],
      ci: Array.isArray(data.ci) ? data.ci : [],
    }
  } catch {
    return { alerts: [], recommendations: [], sentry: [], ci: [] }
  }
}

function saveDismissed(app, data) {
  fs.writeFileSync(storePath(app), `${JSON.stringify(data, null, 2)}\n`, 'utf8')
}

function applyDismissed(snapshot, dismissed) {
  const d = dismissed || { alerts: [], recommendations: [], sentry: [], ci: [] }
  const alertSet = new Set(d.alerts)
  const recSet = new Set(d.recommendations)
  const sentrySet = new Set(d.sentry)
  const ciSet = new Set(d.ci)

  return {
    ...snapshot,
    alerts: (snapshot.alerts || []).filter((a) => !alertSet.has(alertKey(a))),
    recommendations: (snapshot.recommendations || []).filter((r) => !recSet.has(recKey(r))),
    sentry: {
      ...snapshot.sentry,
      issues: (snapshot.sentry?.issues || []).filter((i) => !sentrySet.has(sentryKey(i))),
    },
    ci: {
      ...snapshot.ci,
      runs: (snapshot.ci?.runs || []).filter((r) => !ciSet.has(ciKey(r))),
    },
    dismissedCounts: {
      alerts: d.alerts.length,
      recommendations: d.recommendations.length,
      sentry: d.sentry.length,
      ci: d.ci.length,
    },
  }
}

function alertKey(a) {
  if (a.source === 'sentry' || a.source === 'axiom' || a.source === 'ntfy') {
    return `${a.source}|${a.title || a.message || ''}`
  }
  return `${a.source}|${a.title}|${a.ts || 0}`
}

function recKey(r) {
  return r.action || r.title
}

function sentryKey(i) {
  return String(i.id || i.title)
}

function ciKey(r) {
  return String(r.id || `${r.name}|${r.createdAt}`)
}

module.exports = {
  loadDismissed,
  saveDismissed,
  applyDismissed,
  alertKey,
  recKey,
  sentryKey,
  ciKey,
}
