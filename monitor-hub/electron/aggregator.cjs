const { loadHubConfig, getAlertsLogPath, integrationStatus } = require('./config.cjs')
const { applyDismissed, loadDismissed } = require('./dismissed.cjs')
const { tryGhCliToken, fetchWorkflowRuns, fetchUptimeRuns, fetchLatestRelease } = require('./services/github.cjs')
const { fetchSentry } = require('./services/sentry.cjs')
const { fetchAxiom } = require('./services/axiom.cjs')
const { fetchUptimeRobot } = require('./services/uptimerobot.cjs')
const { fetchCloudflare } = require('./services/cloudflare.cjs')
const { fetchPosthog } = require('./services/posthog.cjs')
const { fetchBusiness } = require('./services/business.cjs')
const { probeHealth, readLocalAlerts, fetchNtfyAlerts } = require('./services/health.cjs')

const latencyHistory = []
const MAX_HISTORY = 96

function computeScore(health, sentry, uptime, ci) {
  if (!health.api.ok || !health.site.ok) return 'critical'
  if (!health.db.ok) return 'warn'
  if (sentry.unresolved > 5) return 'warn'
  if (uptime.monitors?.some((m) => m.status === 9)) return 'critical'
  const failedCi = (ci.runs || []).filter((r) => r.conclusion === 'failure').length
  if (failedCi >= 2) return 'warn'
  return 'ok'
}

function buildRecommendations(snapshot) {
  const recs = []
  const ints = snapshot.integrations

  if (!snapshot.health.api.ok) {
    recs.push({
      severity: 'critical',
      title: 'API offline',
      detail: 'Corre deploy_vm.py ou verifica Cloudflare Tunnel / VM GCP.',
      action: 'api-down',
    })
  }
  if (snapshot.health.api.ms > 2000) {
    recs.push({
      severity: 'warning',
      title: 'Latência API elevada',
      detail: `${snapshot.health.api.ms} ms — rever carga na VM.`,
      action: 'latency',
    })
  }

  const unread = snapshot.business?.pipeline?.unread_total ?? 0
  if (unread > 0) {
    recs.push({
      severity: unread > 5 ? 'warning' : 'warning',
      title: `${unread} pedido(s)/mensagem(ns) por ler`,
      detail: 'Responde no backoffice.',
      action: 'business-unread',
    })
  }

  if (snapshot.sentry.unresolved > 5) {
    recs.push({
      severity: 'warning',
      title: `${snapshot.sentry.unresolved} erros Sentry abertos`,
      detail: snapshot.sentry.issues[0]?.title || 'Ver aba Alertas.',
      action: 'sentry',
    })
  }

  const downMonitors = snapshot.uptime.monitors?.filter((m) => m.status === 9) || []
  for (const m of downMonitors) {
    recs.push({
      severity: 'critical',
      title: `Monitor down: ${m.name}`,
      detail: m.url,
      action: 'uptime',
    })
  }

  const failedCi = (snapshot.ci.runs || []).filter((r) => r.conclusion === 'failure').length
  if (failedCi >= 1) {
    recs.push({
      severity: failedCi >= 2 ? 'warning' : 'info',
      title: 'CI com falha recente',
      detail: `${failedCi} run(s) — ver aba CI/CD (workflow CI, não Uptime).`,
      action: 'ci-fail',
    })
  }

  if (!ints.supabase && !snapshot.business?.configured) {
    recs.push({
      severity: 'warning',
      title: 'Analytics sem dados de negócio',
      detail: 'Configuração → Importar do .env (Supabase).',
      action: 'setup-analytics',
    })
  }

  return recs
}

function mergeAlerts(local, ntfy, sentry, axiom) {
  const out = []
  for (const a of local) {
    out.push({
      severity: a.severity || 'info',
      title: a.title || a.text || 'Alerta local',
      message: a.message || a.detail,
      ts: a.ts ? new Date(a.ts).getTime() : Date.now(),
      source: 'local',
    })
  }
  for (const a of ntfy) out.push(a)
  for (const i of sentry.issues || []) {
    out.push({
      severity: i.level === 'error' ? 'critical' : 'warning',
      title: i.title,
      message: i.culprit,
      ts: i.lastSeen ? new Date(i.lastSeen).getTime() : Date.now(),
      source: 'sentry',
      url: i.permalink,
    })
  }
  if (!sentry.configured || !sentry.issues?.length) {
    for (const e of axiom.recentErrors || []) {
      out.push({
        severity: 'warning',
        title: e.title,
        message: e.message,
        ts: e.ts ? new Date(e.ts).getTime() : Date.now(),
        source: 'axiom',
      })
    }
  }
  return out.sort((a, b) => (b.ts || 0) - (a.ts || 0)).slice(0, 50)
}

async function buildSnapshot(app) {
  const cfg = loadHubConfig(app)
  if (!cfg.github?.token) {
    const ghToken = await tryGhCliToken()
    if (ghToken) cfg.github = { ...cfg.github, token: ghToken }
  }

  const [health, sentry, axiom, uptime, cloudflare, posthog, business] = await Promise.all([
    probeHealth(cfg),
    fetchSentry(cfg),
    fetchAxiom(cfg),
    fetchUptimeRobot(cfg),
    fetchCloudflare(cfg),
    fetchPosthog(cfg),
    fetchBusiness(cfg),
  ])

  let ci = { configured: false, runs: [] }
  let uptimeGh = { configured: false, runs: [] }
  let release = null
  if (cfg.github?.token) {
    const repo = cfg.github.repo || 'tomascms/diomika'
    ;[ci, uptimeGh, release] = await Promise.all([
      fetchWorkflowRuns(cfg.github.token, repo),
      fetchUptimeRuns(cfg.github.token, repo).then((runs) => ({ configured: true, runs })),
      fetchLatestRelease(cfg.github.token, repo),
    ])
  }

  if (health.api.ms != null) {
    latencyHistory.push({ t: Date.now(), ms: health.api.ms })
    if (latencyHistory.length > MAX_HISTORY) latencyHistory.shift()
  }

  const logPath = getAlertsLogPath(app, cfg)
  const localAlerts = readLocalAlerts(logPath)
  const ntfyAlerts = await fetchNtfyAlerts(cfg)
  const alerts = mergeAlerts(localAlerts, ntfyAlerts, sentry, axiom)

  let uptimeFinal = uptime
  if (!uptime.configured) {
    uptimeFinal = {
      configured: true,
      builtin: true,
      monitors: [
        { name: 'API', url: cfg.apiUrl, status: health.api.ok ? 2 : 9, statusLabel: health.api.ok ? 'Up' : 'Down', uptime7d: '—', avgResponse: health.api.ms },
        { name: 'Loja', url: cfg.siteUrl, status: health.site.ok ? 2 : 9, statusLabel: health.site.ok ? 'Up' : 'Down', uptime7d: '—', avgResponse: health.site.ms },
        { name: 'BD', url: `${cfg.apiUrl}/health/ready`, status: health.db.ok ? 2 : 9, statusLabel: health.db.ok ? 'Up' : 'Down', uptime7d: '—', avgResponse: health.db.ms },
      ],
      uptimeRatio: [health.api.ok, health.site.ok, health.db.ok].filter(Boolean).length / 3 * 100,
    }
  }

  const snapshot = {
    ts: Date.now(),
    health,
    score: computeScore(health, sentry, uptimeFinal, ci),
    alerts,
    recommendations: [],
    metrics: {
      latencyHistory: [...latencyHistory],
      errorTrend: axiom.errorRate || [],
      latencyP95: axiom.latencyP95,
      uptimeRatio: uptimeFinal.uptimeRatio,
    },
    sentry,
    axiom,
    uptime: uptimeFinal,
    cloudflare,
    posthog,
    business,
    ci,
    uptimeGh,
    release,
    integrations: integrationStatus(cfg),
  }
  snapshot.recommendations = buildRecommendations(snapshot)
  return applyDismissed(snapshot, loadDismissed(app))
}

module.exports = { buildSnapshot }
