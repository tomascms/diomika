const fs = require('fs')
const path = require('path')
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
const { runSynthetics } = require('./synthetics.cjs')
const { computePosture, computeSlo, computeChanges, correlateDeploy } = require('./posture.cjs')
const { syncFromRecommendations } = require('./incident-store.cjs')
const { getPlaybook } = require('./playbooks.cjs')
const { getUserRoot } = require('./paths.cjs')
const { notifyCritical } = require('./actions.cjs')
const { buildStory, humanizeError } = require('./humanize.cjs')
const { computeBaselines, pushBaselineSample } = require('./baselines.cjs')

const MAX_HISTORY = 120
let prevSnapshot = null
let lastCriticalNotify = 0
let synthCache = { at: 0, data: null }
const SYNTH_TTL_MS = 45_000

function historyPath(app) {
  return path.join(getUserRoot(app), 'hub-metrics-history.json')
}

function loadHistory(app) {
  try {
    return JSON.parse(fs.readFileSync(historyPath(app), 'utf8'))
  } catch {
    return { latency: [], pageviews24h: [], quotes7d: [] }
  }
}

function saveHistory(app, data) {
  try {
    fs.writeFileSync(historyPath(app), JSON.stringify(data, null, 2), 'utf8')
  } catch {
    /* ignore */
  }
}

function computeScore(health, sentry, uptime, ci, synthetics) {
  const reasons = []
  let score = 'ok'
  const bump = (level, reason) => {
    if (reason) reasons.push(reason)
    if (level === 'critical') score = 'critical'
    else if (level === 'warn' && score !== 'critical') score = 'warn'
  }

  if (synthetics?.adminExposed) bump('critical', 'Admin/system exposto')
  if (!health.api.ok) bump('critical', 'API offline')
  if (!health.site.ok) bump('critical', 'Loja offline')
  if (!health.db.ok) bump('warn', 'Base de dados não ready')
  if (synthetics && !synthetics.ok && !synthetics.adminExposed) {
    bump('warn', 'Jornada da loja a falhar')
  }
  if (sentry.unresolved > 5) {
    const recent = (sentry.issues || []).filter((i) => {
      if (!i.lastSeen) return true
      return Date.now() - new Date(i.lastSeen).getTime() < 7 * 24 * 3600 * 1000
    }).length
    if (recent > 5) bump('warn', `${recent} erros recentes no Sentry`)
    else if (sentry.unresolved > 0) reasons.push(`${sentry.unresolved} issues Sentry (maioria antiga)`)
  }
  if (uptime.monitors?.some((m) => m.status === 9)) bump('critical', 'Monitor em baixo')
  const failedCi = (ci.runs || []).filter((r) => r.conclusion === 'failure').length
  if (failedCi >= 2) bump('warn', `${failedCi} falhas de CI`)
  else if (failedCi === 1) reasons.push('1 falha de CI recente')

  return { score, reasons }
}

function enrichRec(r) {
  const pb = getPlaybook(r.action)
  return {
    ...r,
    file: r.file || pb.file || null,
    steps: pb.steps || [],
    actions: pb.actions || [],
  }
}

function buildRecommendations(snapshot) {
  const recs = []

  if (snapshot.synthetics?.adminExposed) {
    recs.push({
      severity: 'critical',
      title: 'Admin ou system acessível publicamente',
      detail: 'A superfície privilegiada respondeu sem o gate do backoffice.',
      action: 'admin-exposed',
    })
  }
  if (!snapshot.health.api.ok) {
    recs.push({
      severity: 'critical',
      title: 'API offline',
      detail: 'A loja não consegue servir catálogo nem pedidos.',
      action: 'api-down',
    })
  }
  if (snapshot.health.api.ok && snapshot.health.api.ms > 2000) {
    recs.push({
      severity: 'warning',
      title: 'API lenta',
      detail: `Resposta em ${snapshot.health.api.ms} ms — a experiência do cliente sofre.`,
      action: 'latency',
    })
  }
  if (snapshot.synthetics?.catalogFail) {
    recs.push({
      severity: 'warning',
      title: 'Catálogo inacessível',
      detail: 'A homepage responde, mas categorias/API de catálogo falharam.',
      action: 'synthetic-fail',
    })
  } else if (snapshot.synthetics && !snapshot.synthetics.ok && !snapshot.synthetics.adminExposed) {
    recs.push({
      severity: 'warning',
      title: 'Jornada sintética falhou',
      detail: (snapshot.synthetics.steps || [])
        .filter((s) => !s.ok)
        .map((s) => s.label)
        .join(', '),
      action: 'synthetic-fail',
    })
  }

  if (snapshot.sentry.unresolved > 5) {
    const recent = (snapshot.sentry.issues || []).filter((i) => {
      if (!i.lastSeen) return true
      return Date.now() - new Date(i.lastSeen).getTime() < 7 * 24 * 3600 * 1000
    })
    if (recent.length > 0) {
      recs.push({
        severity: recent.length > 5 ? 'warning' : 'info',
        title: `${recent.length} erro(s) Sentry recentes`,
        detail: recent
          .slice(0, 3)
          .map((i) => i.title)
          .join(' · '),
        action: 'sentry',
      })
    } else {
      recs.push({
        severity: 'info',
        title: `${snapshot.sentry.unresolved} issues Sentry antigas`,
        detail: 'Sem eventos nos últimos 7 dias — podes resolver em lote no Sentry.',
        action: 'sentry',
      })
    }
  }

  const threats = snapshot.cloudflare?.threats24h
  if (threats != null && threats > 200) {
    recs.push({
      severity: 'warning',
      title: 'Pico de bloqueios na proteção',
      detail: `${threats} eventos de ameaça nas últimas 24h.`,
      action: 'waf-spike',
    })
  }

  for (const m of snapshot.uptime.monitors?.filter((x) => x.status === 9) || []) {
    recs.push({
      severity: 'critical',
      title: `${m.name} em baixo`,
      detail: 'Monitor externo reporta falha.',
      action: 'uptime',
    })
  }

  const failedCi = (snapshot.ci.runs || []).filter((r) => r.conclusion === 'failure').length
  if (failedCi >= 1) {
    recs.push({
      severity: failedCi >= 2 ? 'warning' : 'info',
      title: 'CI com falha recente',
      detail: 'O pipeline de qualidade falhou — não ignores security gate.',
      action: 'ci-fail',
    })
  }

  if (snapshot.deployCorrelation) {
    recs.push({
      severity: 'warning',
      title: 'Possível regressão pós-deploy',
      detail: snapshot.deployCorrelation.message,
      action: 'sentry',
    })
  }

  for (const insight of snapshot.baselines?.insights || []) {
    if (!insight.action) continue
    if (recs.some((r) => r.action === insight.action)) continue
    recs.push({
      severity: insight.severity || 'warning',
      title: insight.title,
      detail: insight.detail,
      action: insight.action,
    })
  }

  if (!snapshot.integrations?.supabase && !snapshot.business?.configured) {
    recs.push({
      severity: 'info',
      title: 'Dados de negócio em falta',
      detail: 'Ligações → Importar do .env (Supabase).',
      action: 'setup-analytics',
    })
  }

  return recs.map(enrichRec)
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
      severity: i.level === 'error' || i.level === 'fatal' ? 'critical' : 'warning',
      title: i.title,
      message: i.culprit,
      ts: i.lastSeen ? new Date(i.lastSeen).getTime() : Date.now(),
      source: 'sentry',
      url: i.permalink,
      issueId: i.id,
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
  return out.sort((a, b) => (b.ts || 0) - (a.ts || 0)).slice(0, 60)
}

function collectIntegrationErrors(parts) {
  const errs = []
  for (const [name, obj] of Object.entries(parts)) {
    // Soft WAF ACL hints are not integration failures when edge metrics work
    if (name === 'cloudflare' && obj?.requests24h != null && !obj?.error) continue
    if (obj?.error) errs.push({ name, error: obj.error, human: humanizeError(name, obj.error) })
  }
  return errs
}

function integrationHealth(parts, integrations) {
  const rows = []
  const add = (id, label, obj, configuredFlag) => {
    const configured = configuredFlag ?? obj?.configured
    let status = 'off'
    let note = 'Não ligado'
    if (configured) {
      if (obj?.error) {
        status = 'bad'
        note = humanizeError(id, obj.error)?.short || 'Com erro'
      } else {
        status = 'ok'
        note = 'OK'
      }
    }
    rows.push({ id, label, status, note, lastOk: status === 'ok' })
  }
  add('health', 'Probes', { configured: true, error: null })
  add('sentry', 'Sentry', parts.sentry)
  add('axiom', 'Axiom', parts.axiom)
  add('posthog', 'PostHog', parts.posthog)
  add(
    'cloudflare',
    'Cloudflare',
    parts.cloudflare?.requests24h != null
      ? { ...parts.cloudflare, error: null }
      : parts.cloudflare,
  )
  add('business', 'Negócio', parts.business)
  add('uptime', 'Uptime', parts.uptime)
  add('github', 'GitHub', { configured: integrations.github, error: null })
  return rows
}

async function getSynthetics(cfg) {
  const now = Date.now()
  if (synthCache.data && now - synthCache.at < SYNTH_TTL_MS) return synthCache.data
  const data = await runSynthetics(cfg)
  synthCache = { at: now, data }
  return data
}

function avgMttr(closed) {
  const withMttr = closed.filter((c) => c.mttrMs != null)
  if (!withMttr.length) return null
  return Math.round(withMttr.reduce((a, c) => a + c.mttrMs, 0) / withMttr.length)
}

async function buildSnapshot(app) {
  const cfg = loadHubConfig(app)
  if (!cfg.github?.token) {
    const ghToken = await tryGhCliToken()
    if (ghToken) cfg.github = { ...cfg.github, token: ghToken }
  }

  const hist = loadHistory(app)
  const latencyHistory = Array.isArray(hist.latency) ? hist.latency.slice(-MAX_HISTORY) : []

  const [health, sentry, axiom, uptime, cloudflare, posthog, business, synthetics] = await Promise.all([
    probeHealth(cfg),
    fetchSentry(cfg),
    fetchAxiom(cfg),
    fetchUptimeRobot(cfg),
    fetchCloudflare(cfg),
    fetchPosthog(cfg),
    fetchBusiness(cfg),
    getSynthetics(cfg),
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
    while (latencyHistory.length > MAX_HISTORY) latencyHistory.shift()
  }

  const logPath = getAlertsLogPath(app, cfg)
  const alerts = mergeAlerts(readLocalAlerts(logPath), await fetchNtfyAlerts(cfg), sentry, axiom)

  let uptimeFinal = uptime
  if (!uptime.configured) {
    uptimeFinal = {
      configured: true,
      builtin: true,
      monitors: [
        {
          name: 'API',
          url: cfg.apiUrl,
          status: health.api.ok ? 2 : 9,
          statusLabel: health.api.ok ? 'Up' : 'Down',
          uptime7d: '—',
          avgResponse: health.api.ms,
        },
        {
          name: 'Loja',
          url: cfg.siteUrl,
          status: health.site.ok ? 2 : 9,
          statusLabel: health.site.ok ? 'Up' : 'Down',
          uptime7d: '—',
          avgResponse: health.site.ms,
        },
        {
          name: 'BD',
          url: `${cfg.apiUrl}/health/ready`,
          status: health.db.ok ? 2 : 9,
          statusLabel: health.db.ok ? 'Up' : 'Down',
          uptime7d: '—',
          avgResponse: health.db.ms,
        },
      ],
      uptimeRatio: ([health.api.ok, health.site.ok, health.db.ok].filter(Boolean).length / 3) * 100,
    }
  }

  const integrations = integrationStatus(cfg)
  const scored = computeScore(health, sentry, uptimeFinal, ci, synthetics)

  const snapshot = {
    ts: Date.now(),
    projectId: cfg.projectId || 'diomika',
    projectName: cfg.projectName || 'Diomika',
    health,
    score: scored.score,
    scoreReasons: scored.reasons,
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
    synthetics,
    posture: null,
    slo: null,
    changes: [],
    deployCorrelation: null,
    baselines: null,
    story: null,
    incidents: { open: [], closed: [] },
    integrations,
    integrationErrors: collectIntegrationErrors({
      sentry,
      axiom,
      uptime,
      cloudflare,
      posthog,
      business,
    }),
    integrationHealth: [],
    version: '1.4.0',
  }

  snapshot.integrationHealth = integrationHealth(
    { sentry, axiom, uptime, cloudflare, posthog, business },
    integrations,
  )
  snapshot.deployCorrelation = correlateDeploy(snapshot)
  snapshot.baselines = computeBaselines(snapshot, hist)
  snapshot.recommendations = buildRecommendations(snapshot)
  snapshot.posture = computePosture(snapshot)
  snapshot.slo = computeSlo(uptimeFinal)
  snapshot.changes = computeChanges(prevSnapshot, snapshot)
  snapshot.story = buildStory(snapshot)

  const incidents = syncFromRecommendations(app, snapshot.recommendations)
  snapshot.incidents = {
    open: incidents.open || [],
    closed: (incidents.closed || []).slice(0, 40),
    openCount: (incidents.open || []).length,
    mttrAvgMs: avgMttr(incidents.closed || []),
  }

  // Conversion approx
  const pv = Number(posthog.pageviews7d ?? posthog.pageviews24h) || 0
  const q = Number(business.quotes?.last7d) || 0
  snapshot.conversion = {
    visitsToQuotes7d: pv > 0 ? Math.round((q / pv) * 10000) / 100 : null,
    visits: pv,
    quotes: q,
  }

  const nextHist = pushBaselineSample(
    { ...hist, latency: latencyHistory },
    snapshot,
  )
  nextHist.latency = latencyHistory
  saveHistory(app, nextHist)

  if (
    scored.score === 'critical' &&
    prevSnapshot?.score !== 'critical' &&
    Date.now() - lastCriticalNotify > 120_000
  ) {
    lastCriticalNotify = Date.now()
    const top = snapshot.story?.items?.find((i) => i.severity === 'critical')
    try {
      notifyCritical(top?.title || 'Estado crítico', top?.detail || snapshot.story?.headline || '')
    } catch {
      /* ignore */
    }
  }

  prevSnapshot = {
    score: snapshot.score,
    sentry: { unresolved: snapshot.sentry.unresolved },
    cloudflare: {
      threats24h: snapshot.cloudflare?.threats24h,
      requests24h: snapshot.cloudflare?.requests24h,
    },
    posthog: { pageviews24h: snapshot.posthog?.pageviews24h },
    ci: snapshot.ci,
    synthetics: { ok: snapshot.synthetics?.ok },
  }

  const dismissed = applyDismissed(snapshot, loadDismissed(app))
  dismissed.story = buildStory(dismissed)
  return dismissed
}

module.exports = { buildSnapshot }
