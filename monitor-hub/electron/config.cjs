const fs = require('fs')
const path = require('path')
const { getLocalConfigPath, getUserRoot, readAlertsLogPath } = require('./paths.cjs')

const DEFAULTS = {
  apiUrl: 'https://api.diomika.com',
  siteUrl: 'https://www.diomika.com',
  pollIntervalSeconds: 30,
  github: {
    clientId: '',
    token: '',
    repo: 'tomascms/diomika',
  },
  sentry: { token: '', org: 'diomika', project: 'python-fastapi', projectId: '4511909963563088', apiHost: 'https://de.sentry.io' },
  axiom: { token: '', dataset: 'diomika', orgId: 'diomika-5pui' },
  uptimerobot: { apiKey: '' },
  cloudflare: { apiToken: '', accountId: '', zoneName: 'diomika.com' },
  posthog: { apiKey: '', projectId: '248877', host: 'https://eu.i.posthog.com' },
  ops: { apiKey: '' },
  supabase: { url: '', key: '' },
}

function parseEnvFile(content) {
  const out = {}
  for (const line of content.split('\n')) {
    const trimmed = line.trim()
    if (!trimmed || trimmed.startsWith('#')) continue
    const idx = trimmed.indexOf('=')
    if (idx < 1) continue
    const key = trimmed.slice(0, idx).trim()
    let val = trimmed.slice(idx + 1).trim()
    if ((val.startsWith('"') && val.endsWith('"')) || (val.startsWith("'") && val.endsWith("'"))) {
      val = val.slice(1, -1)
    }
    out[key] = val
  }
  return out
}

function findEnvPaths(app) {
  const roots = [
    getUserRoot(app),
    path.join(getUserRoot(app), '..', 'diomika'),
    path.join(process.env.USERPROFILE || '', 'Desktop', 'diomika'),
    path.join(__dirname, '..', '..'),
  ]
  const seen = new Set()
  const files = []
  for (const root of roots) {
    const p = path.resolve(root, '.env')
    if (seen.has(p) || !fs.existsSync(p)) continue
    seen.add(p)
    files.push(p)
  }
  return files
}

function mergeFromEnv(cfg, env) {
  const next = { ...cfg }
  if (env.ALERT_WEBHOOK_URL && !next.ntfyTopicJsonUrl) {
    const m = env.ALERT_WEBHOOK_URL.match(/ntfy\.sh\/([^/?#]+)/i)
    if (m) next.ntfyTopicJsonUrl = `https://ntfy.sh/${m[1]}/json?poll=1`
  }
  if (env.AXIOM_TOKEN && !next.axiom?.token) {
    next.axiom = { ...next.axiom, token: env.AXIOM_TOKEN }
  }
  if (env.AXIOM_DATASET && next.axiom) next.axiom.dataset = env.AXIOM_DATASET
  if (env.CLOUDFLARE_API_TOKEN && !next.cloudflare?.apiToken) {
    next.cloudflare = { ...next.cloudflare, apiToken: env.CLOUDFLARE_API_TOKEN }
  }
  if (env.CLOUDFLARE_ACCOUNT_ID && next.cloudflare) {
    next.cloudflare.accountId = env.CLOUDFLARE_ACCOUNT_ID
  }
  if (env.POSTHOG_PERSONAL_API_KEY) {
    next.posthog = { ...next.posthog, apiKey: env.POSTHOG_PERSONAL_API_KEY }
  } else if (env.VITE_POSTHOG_KEY && !next.posthog?.apiKey) {
    next.posthog = { ...next.posthog, apiKey: env.VITE_POSTHOG_KEY }
  }
  if (env.VITE_POSTHOG_HOST && next.posthog) next.posthog.host = env.VITE_POSTHOG_HOST
  if (env.POSTHOG_PROJECT_ID && next.posthog) next.posthog.projectId = env.POSTHOG_PROJECT_ID
  if (env.SENTRY_AUTH_TOKEN && !next.sentry?.token) {
    next.sentry = { ...next.sentry, token: env.SENTRY_AUTH_TOKEN }
  }
  if (next.sentry && !next.sentry.apiHost) next.sentry.apiHost = 'https://de.sentry.io'
  if (env.UPTIMEROBOT_API_KEY && !next.uptimerobot?.apiKey) {
    next.uptimerobot = { ...next.uptimerobot, apiKey: env.UPTIMEROBOT_API_KEY }
  }
  if (env.API_OPS_KEY && !next.ops?.apiKey) {
    next.ops = { ...next.ops, apiKey: env.API_OPS_KEY }
  }
  if (env.SUPABASE_URL && !next.supabase?.url) {
    next.supabase = { ...next.supabase, url: env.SUPABASE_URL }
  }
  if (env.SUPABASE_KEY && !next.supabase?.key) {
    next.supabase = { ...next.supabase, key: env.SUPABASE_KEY }
  }
  return next
}

function loadHubConfig(app) {
  const localPath = getLocalConfigPath(app)
  let cfg = { ...DEFAULTS }
  if (fs.existsSync(localPath)) {
    try {
      const parsed = JSON.parse(fs.readFileSync(localPath, 'utf8'))
      cfg = {
        ...cfg,
        ...parsed,
        github: { ...DEFAULTS.github, ...(parsed.github || {}) },
        sentry: { ...DEFAULTS.sentry, ...(parsed.sentry || {}) },
        axiom: { ...DEFAULTS.axiom, ...(parsed.axiom || {}) },
        uptimerobot: { ...DEFAULTS.uptimerobot, ...(parsed.uptimerobot || {}) },
        cloudflare: { ...DEFAULTS.cloudflare, ...(parsed.cloudflare || {}) },
        posthog: { ...DEFAULTS.posthog, ...(parsed.posthog || {}) },
        ops: { ...DEFAULTS.ops, ...(parsed.ops || {}) },
        supabase: { ...DEFAULTS.supabase, ...(parsed.supabase || {}) },
      }
    } catch {
      /* keep defaults */
    }
  }
  for (const envPath of findEnvPaths(app)) {
    try {
      cfg = mergeFromEnv(cfg, parseEnvFile(fs.readFileSync(envPath, 'utf8')))
    } catch {
      /* skip */
    }
  }
  return cfg
}

function saveHubConfig(app, partial) {
  const localPath = getLocalConfigPath(app)
  const current = loadHubConfig(app)

  const mergeSection = (key, secretFields = ['token', 'apiKey', 'apiToken']) => {
    if (!partial[key]) return current[key]
    const next = { ...current[key], ...partial[key] }
    for (const field of secretFields) {
      if (partial[key][field] === '***' || partial[key][field] === '') {
        next[field] = current[key]?.[field] || ''
      }
    }
    return next
  }

  const merged = {
    ...current,
    ...partial,
    github: mergeSection('github'),
    sentry: mergeSection('sentry'),
    axiom: mergeSection('axiom'),
    uptimerobot: mergeSection('uptimerobot', ['apiKey']),
    cloudflare: mergeSection('cloudflare', ['apiToken']),
    posthog: mergeSection('posthog', ['apiKey']),
    ops: mergeSection('ops', ['apiKey']),
    supabase: mergeSection('supabase', ['key']),
  }
  fs.writeFileSync(localPath, `${JSON.stringify(merged, null, 2)}\n`, 'utf8')
  return merged
}

function getAlertsLogPath(app, cfg) {
  return readAlertsLogPath(app, cfg)
}

function integrationStatus(cfg) {
  return {
    github: Boolean(cfg.github?.token),
    sentry: Boolean(cfg.sentry?.token),
    axiom: Boolean(cfg.axiom?.token),
    uptimerobot: Boolean(cfg.uptimerobot?.apiKey),
    cloudflare: Boolean(cfg.cloudflare?.apiToken),
    posthog: Boolean(cfg.posthog?.apiKey),
    ntfy: Boolean(cfg.ntfyTopicJsonUrl),
    ops: Boolean(cfg.ops?.apiKey),
    supabase: Boolean(cfg.supabase?.url && cfg.supabase?.key),
  }
}

/** Grava credenciais fundidas do .env no config.local.json (exe portable). */
function persistMergedSecrets(app) {
  const localPath = getLocalConfigPath(app)
  const merged = loadHubConfig(app)
  let current = {}
  if (fs.existsSync(localPath)) {
    try {
      current = JSON.parse(fs.readFileSync(localPath, 'utf8'))
    } catch {
      current = {}
    }
  }
  const patch = {
    ...current,
    supabase: merged.supabase,
    ops: merged.ops,
    posthog: { ...(current.posthog || {}), ...merged.posthog },
    sentry: { ...(current.sentry || {}), ...merged.sentry },
    axiom: { ...(current.axiom || {}), ...merged.axiom },
    uptimerobot: { ...(current.uptimerobot || {}), ...merged.uptimerobot },
    cloudflare: { ...(current.cloudflare || {}), ...merged.cloudflare },
    github: { ...(current.github || {}), token: merged.github?.token || current.github?.token },
    ntfyTopicJsonUrl: merged.ntfyTopicJsonUrl || current.ntfyTopicJsonUrl,
    alertsLogPath: merged.alertsLogPath || current.alertsLogPath,
  }
  fs.writeFileSync(localPath, `${JSON.stringify(patch, null, 2)}\n`, 'utf8')
  return patch
}

module.exports = {
  DEFAULTS,
  loadHubConfig,
  saveHubConfig,
  getAlertsLogPath,
  integrationStatus,
  persistMergedSecrets,
  getLocalConfigPath,
}
