let snapshot = null
let latencyChart = null
let errorsChart = null
let visitsChart = null
let businessChart = null
let lastUpdate = 0

const views = {
  overview: { title: 'Visão geral', sub: 'Saúde do sistema — o que precisa de atenção agora' },
  analytics: { title: 'Analytics', sub: 'Visitas, orçamentos e contactos para o negócio' },
  alerts: { title: 'Alertas', sub: 'Problemas activos — ntfy, Sentry e logs' },
  metrics: { title: 'Infraestrutura', sub: 'Uptime, Cloudflare, Sentry e edge' },
  cicd: { title: 'CI / CD', sub: 'Deploys e GitHub Actions' },
  setup: { title: 'Configuração', sub: 'Liga APIs uma vez — o hub faz o resto' },
}

function esc(value) {
  return String(value ?? '')
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
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

function toast(msg) {
  const el = document.getElementById('toast')
  el.textContent = msg
  el.classList.remove('hidden')
  clearTimeout(toast._t)
  toast._t = setTimeout(() => el.classList.add('hidden'), 3200)
}

async function clearTab(tab, s) {
  let items = []
  if (tab === 'alerts') items = (s.alerts || []).map(alertKey)
  if (tab === 'overview') items = (s.recommendations || []).map(recKey)
  if (tab === 'metrics') items = (s.sentry?.issues || []).map(sentryKey)
  if (tab === 'cicd') {
    items = (s.ci?.runs || []).filter((r) => r.conclusion === 'failure').map(ciKey)
    if (!items.length) items = (s.ci?.runs || []).map(ciKey)
  }
  if (!items.length) {
    toast('Nada a limpar nesta aba.')
    return
  }
  const res = await window.hub.dismissTab(tab, items)
  if (res?.snapshot) renderAll(res.snapshot)
  toast('Lista limpa — itens ocultos até voltarem a aparecer nas APIs.')
}

document.querySelectorAll('[data-clear-tab]').forEach((btn) => {
  btn.addEventListener('click', () => {
    if (!snapshot) return
    clearTab(btn.dataset.clearTab, snapshot)
  })
})

function fmtTime(ts) {
  if (!ts) return '—'
  return new Date(ts).toLocaleString('pt-PT')
}

function pill(label, kind) {
  return `<span class="pill ${kind}">${esc(label)}</span>`
}
function healthKind(ok) {
  return ok ? 'ok' : 'bad'
}

function renderHealthCards(s) {
  const h = s.health
  document.getElementById('health-cards').innerHTML = [
    { title: 'API', ok: h.api.ok, detail: `${h.api.ms ?? '—'} ms · v${h.api.version || '?'}` },
    { title: 'Base de dados', ok: h.db.ok, detail: `${h.db.ms ?? '—'} ms · /health/ready` },
    { title: 'Loja', ok: h.site.ok, detail: `${h.site.ms ?? '—'} ms · Pages` },
  ]
    .map(
      (c) => `<div class="card"><div class="card-head"><span class="card-title">${esc(c.title)}</span>${pill(c.ok ? 'OK' : 'FALHA', healthKind(c.ok))}</div><div class="muted">${esc(c.detail)}</div></div>`,
    )
    .join('')
}

function renderIntelCards(s) {
  const b = s.business || {}
  const rows = [
    { t: 'Visitas 24 h', v: s.posthog.pageviews24h ?? '—', k: 'ok' },
    { t: 'Orçamentos 7 d', v: b.quotes?.last7d ?? '—', k: (b.quotes?.last7d || 0) > 0 ? 'warn' : 'ok' },
    { t: 'Por ler', v: b.pipeline?.unread_total ?? '—', k: (b.pipeline?.unread_total || 0) > 0 ? 'warn' : 'ok' },
    { t: 'Erros Sentry', v: s.sentry.configured ? s.sentry.unresolved : '—', k: s.sentry.unresolved > 0 ? 'warn' : 'ok' },
    { t: 'Uptime', v: s.metrics.uptimeRatio != null ? `${s.metrics.uptimeRatio}%` : '—', k: 'ok' },
    { t: 'CI falhou', v: (s.ci.runs || []).filter((r) => r.conclusion === 'failure').length, k: 'warn' },
  ]
  document.getElementById('intel-cards').innerHTML = rows
    .map((r) => `<div class="card"><div class="card-head"><span class="card-title">${esc(r.t)}</span>${pill(String(r.v), r.k)}</div></div>`)
    .join('')
}
function renderKpis(s) {
  const crit = s.alerts.filter((a) => a.severity === 'critical').length
  document.getElementById('kpi-strip').innerHTML = [
    { label: 'Score', value: s.score.toUpperCase() },
    { label: 'Alertas', value: s.alerts.length },
    { label: 'Críticos', value: crit },
    { label: 'API ms', value: s.health.api.ms ?? '—' },
  ]
    .map((k) => `<div class="kpi"><div class="label">${k.label}</div><div class="value">${k.value}</div></div>`)
    .join('')

  const dot = document.getElementById('score-dot')
  dot.className = `brand-dot ${s.score === 'ok' ? 'ok' : s.score === 'warn' ? 'warn' : 'bad'}`

  const badge = document.getElementById('alert-badge')
  badge.textContent = String(s.alerts.length)
  badge.classList.toggle('hot', crit > 0)
}

function renderRecs(s) {
  const el = document.getElementById('recommendations')
  const head = el.previousElementSibling
  if (!s.recommendations?.length) {
    el.innerHTML = ''
    if (head?.classList?.contains('panel-head-row')) head.style.display = 'none'
    return
  }
  if (head?.classList?.contains('panel-head-row')) head.style.display = 'flex'
  el.innerHTML = s.recommendations
    .slice(0, 4)
    .map(
      (r) =>
        `<div class="rec ${r.severity}"><strong>${esc(r.title)}</strong>${esc(r.detail)}</div>`,
    )
    .join('')
}

function renderAlerts(s) {
  const feed = document.getElementById('alert-feed')
  if (!s.alerts.length) {
    feed.innerHTML = '<p class="muted">Sem alertas — sistema estável.</p>'
    return
  }
  feed.innerHTML = s.alerts
    .map(
      (a) => `<div class="alert-item ${a.severity || 'info'}">
      <div class="alert-src">${esc(a.source || '—')}</div>
      <div><strong>${esc(a.title || 'Alerta')}</strong><br><span class="muted">${esc(a.message || '')}</span></div>
      <div class="muted">${fmtTime(a.ts)}</div>
    </div>`,
    )
    .join('')
}

function renderUptime(s) {
  const el = document.getElementById('uptime-table')
  if (!s.uptime.configured) {
    el.innerHTML = '<p class="muted">Configura uptimerobot.apiKey</p>'
    return
  }
  if (!s.uptime.monitors?.length) {
    el.innerHTML = '<p class="muted">Sem monitores</p>'
    return
  }
  el.innerHTML = `<table class="data"><thead><tr><th>Monitor</th><th>Estado</th><th>7d</th><th>ms</th></tr></thead><tbody>${s.uptime.monitors
    .map(
      (m) =>
        `<tr><td>${m.name}</td><td>${pill(m.statusLabel, m.status === 2 ? 'ok' : m.status === 9 ? 'bad' : 'warn')}</td><td>${m.uptime7d}</td><td>${m.avgResponse ?? '—'}</td></tr>`,
    )
    .join('')}</tbody></table>`
}

function renderEdge(s) {
  document.getElementById('edge-metrics').innerHTML = [
    ['Zona Cloudflare', s.cloudflare.zoneName || '—'],
    ['Pedidos 24h', s.cloudflare.requests24h ?? '—'],
    ['Ameaças 24h', s.cloudflare.threats24h ?? '—'],
    ['DAU PostHog', s.posthog.dau ?? '—'],
    ['Pageviews 24h', s.posthog.pageviews24h ?? '—'],
  ]
    .map(([k, v]) => `<div class="metric-row"><span>${k}</span><strong>${v}</strong></div>`)
    .join('')
}

function renderUptimeGh(s) {
  const el = document.getElementById('uptime-gh-table')
  if (!el) return
  if (!s.uptimeGh?.configured) {
    el.innerHTML = '<p class="muted">Liga GitHub para ver o monitor Uptime</p>'
    return
  }
  if (!s.uptimeGh.runs?.length) {
    el.innerHTML = '<p class="muted">Sem runs recentes</p>'
    return
  }
  el.innerHTML = `<table class="data"><thead><tr><th>Run</th><th>Estado</th><th>Quando</th></tr></thead><tbody>${s.uptimeGh.runs
    .map((r) => {
      const st = r.conclusion || r.status
      const kind = r.conclusion === 'success' ? 'ok' : r.conclusion === 'failure' ? 'bad' : 'warn'
      return `<tr><td>${r.name}</td><td>${pill(st, kind)}</td><td>${fmtTime(r.createdAt)}</td></tr>`
    })
    .join('')}</tbody></table>`
}

function renderSentryTable(s) {
  const el = document.getElementById('sentry-table')
  if (!s.sentry.configured) {
    el.innerHTML = '<p class="muted">Token Sentry em falta</p>'
    return
  }
  if (!s.sentry.issues?.length) {
    el.innerHTML = '<p class="muted">Nenhum erro aberto 🎉</p>'
    return
  }
  el.innerHTML = `<table class="data"><thead><tr><th>Erro</th><th>Nível</th><th>Count</th><th>Visto</th></tr></thead><tbody>${s.sentry.issues
    .map(
      (i) =>
        `<tr><td>${i.title}</td><td>${i.level}</td><td>${i.count}</td><td>${fmtTime(i.lastSeen)}</td></tr>`,
    )
    .join('')}</tbody></table>`
}

function renderCi(s) {
  const rel = document.getElementById('release-card')
  if (s.release) {
    rel.innerHTML = `<h2>Último release</h2><p><strong>${s.release.tag}</strong> — ${s.release.name || ''}</p><p class="muted">${fmtTime(s.release.publishedAt)}</p>`
  } else {
    rel.innerHTML = '<h2>Release</h2><p class="muted">Liga GitHub para ver releases</p>'
  }

  const el = document.getElementById('ci-table')
  if (!s.ci.configured) {
    el.innerHTML = '<p class="muted">Liga GitHub (CLI ou Device Flow)</p>'
    return
  }
  el.innerHTML = `<table class="data"><thead><tr><th>Workflow</th><th>Branch</th><th>Estado</th><th>Quando</th></tr></thead><tbody>${(s.ci.runs || [])
    .map((r) => {
      const st = r.conclusion || r.status
      const kind = r.conclusion === 'success' ? 'ok' : r.conclusion === 'failure' ? 'bad' : 'warn'
      return `<tr><td>${r.name}</td><td>${r.branch}</td><td>${pill(st, kind)}</td><td>${fmtTime(r.createdAt)}</td></tr>`
    })
    .join('')}</tbody></table>`
}

function upsertChart(chartRef, canvasId, cfg) {
  const ctx = document.getElementById(canvasId)
  if (!ctx) return chartRef
  if (chartRef) {
    chartRef.data = cfg.data
    chartRef.options = cfg.options
    chartRef.update('none')
    return chartRef
  }
  return new Chart(ctx, cfg)
}

function renderCharts(s) {
  const lat = s.metrics.latencyHistory || []
  latencyChart = upsertChart(latencyChart, 'chart-latency', {
    type: 'line',
    data: {
      labels: lat.map((p) => new Date(p.t).toLocaleTimeString('pt-PT', { hour: '2-digit', minute: '2-digit' })),
      datasets: [{
        label: 'ms',
        data: lat.map((p) => p.ms),
        borderColor: '#3d8bfd',
        backgroundColor: 'rgba(61,139,253,.12)',
        fill: true,
        tension: 0.3,
        pointRadius: 0,
      }],
    },
    options: {
      responsive: true,
      plugins: { legend: { display: false } },
      scales: {
        x: { ticks: { color: '#8b9bb0', maxTicksLimit: 8 }, grid: { color: '#243041' } },
        y: { ticks: { color: '#8b9bb0' }, grid: { color: '#243041' } },
      },
    },
  })
  const err = s.metrics.errorTrend || []
  errorsChart = upsertChart(errorsChart, 'chart-errors', {
    type: 'bar',
    data: {
      labels: err.map((e) => {
        try {
          return new Date(e.hour).toLocaleTimeString('pt-PT', { hour: '2-digit' })
        } catch {
          return String(e.hour)
        }
      }),
      datasets: [{
        label: 'Erros',
        data: err.map((e) => e.count),
        backgroundColor: 'rgba(248,113,113,.55)',
      }],
    },
    options: chartOpts(false),
  })
}

function renderAnalytics(s) {
  const b = s.business || {}
  const ph = s.posthog || {}
  const lead = document.getElementById('analytics-lead')
  if (b.error) {
    lead.textContent = `Dados indisponíveis: ${b.error}`
  } else if (!b.configured) {
    lead.textContent = 'Configuração → Importar do .env (lê Supabase automaticamente).'
  } else if (b.apiPending) {
    lead.textContent = 'Dados via Supabase (API ainda não deployada). Visitas + negócio actualizados a cada 30 s.'
  } else {
    lead.textContent = `Negócio via ${b.source === 'api' ? 'API' : 'Supabase'} · actualizado a cada 30 s.`
  }

  const kpis = [
    { label: 'Visitas 24 h', value: ph.pageviews24h ?? '—', hint: 'Utilizadores na loja' },
    { label: 'Orçamentos 7 d', value: b.quotes?.last7d ?? '—', hint: `${b.quotes?.unread ?? 0} por ler` },
    { label: 'Contactos 7 d', value: b.contacts?.last7d ?? '—', hint: `${b.contacts?.unread ?? 0} por ler` },
    { label: 'Encomendas 7 d', value: b.orders?.last7d ?? '—', hint: 'Pedidos internos B2B' },
  ]
  document.getElementById('analytics-kpis').innerHTML = kpis
    .map(
      (k) => `<div class="card analytics-kpi"><div class="label">${esc(k.label)}</div><div class="value">${esc(k.value)}</div><div class="hint">${esc(k.hint)}</div></div>`,
    )
    .join('')

  const hourly = ph.hourly || []
  visitsChart = upsertChart(visitsChart, 'chart-visits', {
    type: 'bar',
    data: {
      labels: hourly.map((_, i) => `${i}h`),
      datasets: [{
        label: 'Pageviews',
        data: hourly,
        backgroundColor: 'rgba(61,139,253,.55)',
      }],
    },
    options: chartOpts(false),
  })

  const bizLabels = ['Orçamentos', 'Contactos', 'Encomendas']
  const bizData = [b.quotes?.last7d || 0, b.contacts?.last7d || 0, b.orders?.last7d || 0]
  businessChart = upsertChart(businessChart, 'chart-business', {
    type: 'bar',
    data: {
      labels: bizLabels,
      datasets: [{
        label: 'Últimos 7 dias',
        data: bizData,
        backgroundColor: ['rgba(61,211,140,.55)', 'rgba(245,158,11,.55)', 'rgba(147,112,255,.55)'],
      }],
    },
    options: chartOpts(false),
  })

  const pv = Number(ph.pageviews24h) || 0
  const quotes7 = Number(b.quotes?.last7d) || 0
  const conv = pv > 0 ? `${((quotes7 / pv) * 100).toFixed(2)}%` : '—'
  const insights = [
    {
      title: 'Funil simples',
      text: `${pv} visitas → ${quotes7} orçamentos (7 d). Taxa visita→orçamento: ${conv}.`,
      value: conv,
    },
    {
      title: 'Inbox comercial',
      text: `${b.pipeline?.unread_total ?? 0} itens por ler (orçamentos + contactos). Responde no backoffice.`,
      value: b.pipeline?.unread_total ?? 0,
    },
    {
      title: 'Hoje',
      text: `${b.quotes?.today ?? 0} orçamentos e ${b.contacts?.today ?? 0} contactos recebidos hoje.`,
      value: (b.quotes?.today || 0) + (b.contacts?.today || 0),
    },
    {
      title: 'Tráfego',
      text: ph.dau != null ? `${ph.dau} visitantes únicos nas últimas 24 h.` : 'DAU indisponível — normal com pouco tráfego.',
      value: ph.dau ?? '—',
    },
  ]
  document.getElementById('analytics-insights').innerHTML = insights
    .map(
      (row) => `<div class="insight-row"><div><strong>${esc(row.title)}</strong><span class="muted">${esc(row.text)}</span></div><strong>${esc(row.value)}</strong></div>`,
    )
    .join('')
}

function chartOpts(legend) {
  return {
    responsive: true,
    plugins: { legend: { display: legend } },
    scales: {
      x: { ticks: { color: '#8b9bb0' }, grid: { color: '#243041' } },
      y: { ticks: { color: '#8b9bb0', precision: 0 }, grid: { color: '#243041' } },
    },
  }
}

function renderAll(s) {
  snapshot = s
  lastUpdate = Date.now()
  document.getElementById('live-indicator').textContent = `● Actualizado ${new Date().toLocaleTimeString('pt-PT')}`
  document.getElementById('live-indicator').classList.remove('stale')
  renderKpis(s)
  renderRecs(s)
  renderHealthCards(s)
  renderIntelCards(s)
  renderCharts(s)
  renderAnalytics(s)
  renderAlerts(s)
  renderUptime(s)
  renderEdge(s)
  renderUptimeGh(s)
  renderSentryTable(s)
  renderCi(s)
}

async function renderIntegrations() {
  const cfg = await window.hub.getConfig()
  const names = {
    github: 'GitHub',
    sentry: 'Sentry',
    axiom: 'Axiom',
    uptimerobot: 'UptimeRobot',
    cloudflare: 'Cloudflare',
    posthog: 'PostHog',
    supabase: 'Supabase',
    ops: 'API ops',
    ntfy: 'ntfy',
  }
  document.getElementById('integration-grid').innerHTML = Object.entries(names)
    .map(
      ([k, label]) =>
        `<div class="int-chip ${cfg.integrations?.[k] ? 'on' : 'off'}">${label}: ${cfg.integrations?.[k] ? 'ligado' : 'pendente'}</div>`,
    )
    .join('')
}

function switchView(name) {
  document.querySelectorAll('.nav-btn').forEach((b) => b.classList.toggle('active', b.dataset.view === name))
  document.querySelectorAll('.view').forEach((v) => v.classList.remove('active'))
  document.getElementById(`view-${name}`).classList.add('active')
  const meta = views[name]
  document.getElementById('view-title').textContent = meta.title
  document.getElementById('view-sub').textContent = meta.sub
  if (name === 'setup') renderIntegrations()
}

document.querySelectorAll('.nav-btn').forEach((btn) => {
  btn.addEventListener('click', () => switchView(btn.dataset.view))
})

document.getElementById('refresh-btn').addEventListener('click', async () => {
  const s = await window.hub.refreshNow()
  renderAll(s)
})

document.getElementById('clear-all-btn').addEventListener('click', async () => {
  const res = await window.hub.dismissAll()
  if (res?.snapshot) renderAll(res.snapshot)
  toast('Todas as listas limpas neste hub.')
})

document.getElementById('btn-import-env').addEventListener('click', async () => {
  await window.hub.importEnv()
  await renderIntegrations()
  const s = await window.hub.refreshNow()
  renderAll(s)
  toast('Credenciais importadas do .env.')
})

document.getElementById('btn-open-config').addEventListener('click', () => window.hub.openConfigFile())

document.getElementById('btn-gh-cli').addEventListener('click', async () => {
  const r = await window.hub.githubTryGhCli()
  if (r.ok) {
    toast('GitHub ligado via CLI.')
    await renderIntegrations()
  } else {
    toast('GitHub CLI não detectado — instala gh auth login.')
  }
})

document.getElementById('btn-gh-device').addEventListener('click', async () => {
  const box = document.getElementById('gh-device-box')
  box.classList.remove('hidden')
  box.textContent = 'A pedir código…'
  const flow = await window.hub.githubStartDevice()
  if (flow.error) {
    box.textContent = flow.error
    return
  }
  box.innerHTML = `Abre <a href="${flow.verificationUri}" target="_blank">${flow.verificationUri}</a> e introduz o código: <strong style="font-size:1.4rem">${flow.userCode}</strong><br><span class="muted">A aguardar autorização…</span>`
  const res = await window.hub.githubPollDevice({
    clientId: flow.clientId,
    deviceCode: flow.deviceCode,
    interval: flow.interval,
  })
  if (res.ok) {
    box.textContent = 'GitHub ligado com sucesso.'
    await renderIntegrations()
  } else {
    box.textContent = res.error || 'Falhou'
  }
})

document.getElementById('setup-form').addEventListener('submit', async (e) => {
  e.preventDefault()
  const fd = new FormData(e.target)
  await window.hub.saveConfig({
    sentry: { token: fd.get('sentryToken') || undefined },
    uptimerobot: { apiKey: fd.get('uptimeKey') || undefined },
    posthog: { apiKey: fd.get('posthogKey') || undefined },
    ops: { apiKey: fd.get('opsKey') || undefined },
    github: { clientId: fd.get('githubClientId') || undefined },
  })
  await renderIntegrations()
  toast('Configuração guardada.')
})

document.getElementById('gh-cli-link').addEventListener('click', (e) => {
  e.preventDefault()
  window.open('https://cli.github.com/', '_blank')
})

window.hub.onSnapshot(renderAll)
window.hub.onSnapshotError((msg) => {
  document.getElementById('live-indicator').textContent = `● Erro: ${msg}`
  document.getElementById('live-indicator').classList.add('stale')
})

setInterval(() => {
  if (lastUpdate && Date.now() - lastUpdate > 90000) {
    document.getElementById('live-indicator').classList.add('stale')
  }
}, 10000)

renderIntegrations()
