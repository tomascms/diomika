let snapshot = null
let latencyChart = null
let errorsChart = null
let visitsChart = null
let businessChart = null
let dailyChart = null
let edgeChart = null
let lastUpdate = 0
let selectedIncident = null

const views = {
  overview: { title: 'Visão geral', sub: 'Centro de comando — estado do cliente em 30 segundos' },
  analytics: { title: 'Analytics', sub: 'Visitas, funil e negócio' },
  security: { title: 'Segurança', sub: 'Postura, ataques e jornadas' },
  alerts: { title: 'Incidentes', sub: 'Histórico, playbooks e feed' },
  metrics: { title: 'Infra', sub: 'API, latência, monitores e Sentry' },
  cicd: { title: 'CI / CD', sub: 'Releases e GitHub Actions' },
  setup: { title: 'Ligações', sub: 'Credenciais e integrações' },
}

const ACTION_LABELS = {
  'run-health': 'Health',
  'run-verify': 'Verify production',
  'run-monitor-check': 'Monitor check',
  'copy-cursor-prompt': 'Prompt Cursor',
  'sentry-resolve': 'Resolver Sentry',
  'open-path': 'Abrir ficheiro',
}

function esc(v) {
  return String(v ?? '')
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

function fmtTime(ts) {
  if (!ts) return '—'
  return new Date(ts).toLocaleString('pt-PT')
}

function fmtDuration(ms) {
  if (ms == null) return '—'
  const m = Math.round(ms / 60000)
  if (m < 60) return `${m} min`
  const h = Math.round(m / 60)
  return h < 48 ? `${h} h` : `${Math.round(h / 24)} d`
}

function pill(label, kind) {
  return `<span class="pill ${kind}">${esc(label)}</span>`
}

function scoreClass(score) {
  if (score === 'ok') return 'ok'
  if (score === 'warn') return 'warn'
  return 'bad'
}

function empty(title, text) {
  return `<div class="empty-state"><strong>${esc(title)}</strong>${esc(text)}</div>`
}

function num(v) {
  return v == null || v === '' ? '—' : String(v)
}

function fmtBytes(n) {
  if (n == null || n === '') return '—'
  const x = Number(n)
  if (!Number.isFinite(x)) return '—'
  if (x < 1024) return `${x} B`
  if (x < 1024 ** 2) return `${(x / 1024).toFixed(1)} KB`
  if (x < 1024 ** 3) return `${(x / 1024 ** 2).toFixed(1)} MB`
  return `${(x / 1024 ** 3).toFixed(2)} GB`
}

function openUrl(url) {
  if (url) window.hub.openExternal(url)
}

async function clearTab(tab, s) {
  let items = []
  if (tab === 'alerts') items = (s.alerts || []).map(alertKey)
  if (tab === 'overview') items = (s.recommendations || []).map(recKey)
  if (tab === 'metrics') items = (s.sentry?.issues || []).map(sentryKey)
  if (tab === 'cicd') {
    items = (s.ci?.runs || []).filter((r) => r.conclusion === 'failure').map(ciKey)
  }
  if (!items.length) {
    toast('Nada a ocultar.')
    return
  }
  const res = await window.hub.dismissTab(tab, items)
  if (res?.snapshot) renderAll(res.snapshot)
  toast('Ocultado.')
}

document.querySelectorAll('[data-clear-tab]').forEach((btn) => {
  btn.addEventListener('click', () => snapshot && clearTab(btn.dataset.clearTab, snapshot))
})

/* ---------- Overview / control tower ---------- */
function renderTower(s) {
  const story = s.story || { tone: s.score, headline: '', items: [] }
  const tone = story.tone === 'ok' ? 'ok' : story.tone === 'critical' ? 'critical' : 'warn'
  const label = s.score === 'ok' ? 'OK' : s.score === 'warn' ? 'ATENÇÃO' : 'CRÍTICO'

  document.getElementById('tower-hero').innerHTML = `
    <div class="hero-score ${tone}">
      <div class="score-label">Estado do cliente</div>
      <div class="score-value">${esc(label)}</div>
      <div class="hero-headline">${esc(story.headline || '—')}</div>
      <div class="muted" style="margin-top:8px">Postura ${esc(s.posture?.score ?? '—')}/100 · SLO ${esc(s.slo?.uptime30d != null ? s.slo.uptime30d + '%' : '—')}</div>
    </div>
    <div class="hero-meta">
      <div class="card"><div class="card-head"><span class="card-title">API</span>${pill(s.health.api.ok ? 'OK' : 'DOWN', s.health.api.ok ? 'ok' : 'bad')}</div><div class="muted">${esc(s.health.api.ms ?? '—')} ms</div></div>
      <div class="card"><div class="card-head"><span class="card-title">Loja</span>${pill(s.health.site.ok ? 'OK' : 'DOWN', s.health.site.ok ? 'ok' : 'bad')}</div><div class="muted">${esc(s.health.site.ms ?? '—')} ms</div></div>
      <div class="card"><div class="card-head"><span class="card-title">Admin</span>${pill(s.synthetics?.adminExposed ? 'EXPOSTO' : 'OK', s.synthetics?.adminExposed ? 'bad' : 'ok')}</div><div class="muted">Gate público</div></div>
      <div class="card"><div class="card-head"><span class="card-title">Sintéticos</span>${pill(s.synthetics?.ok ? 'OK' : 'FALHA', s.synthetics?.ok ? 'ok' : 'bad')}</div><div class="muted">Funil loja</div></div>
    </div>`

  document.getElementById('int-strip').innerHTML = (s.integrationHealth || [])
    .map((r) => `<span class="int-pill ${esc(r.status)}" title="${esc(r.note)}">${esc(r.label)}</span>`)
    .join('')

  const edge = s.cloudflare?.requests24h
  const threats = s.cloudflare?.threats24h
  const visits = s.posthog?.pageviews24h
  const unread = s.business?.pipeline?.unread_total
  const ratio = s.cloudflare?.threatRatio
  document.getElementById('tower-nums').innerHTML = [
    {
      t: 'Pedidos edge 24h',
      v: num(edge),
      s: edge != null ? `${num(threats)} ameaças` : 'Tráfego Cloudflare',
    },
    {
      t: 'Taxa ameaça',
      v: ratio != null ? `${ratio}%` : '—',
      s: ratio != null && ratio > 30 ? 'Alta — WAF a trabalhar' : 'Pedidos vs ameaças',
    },
    {
      t: 'Visitas analytics 24h',
      v: num(visits),
      s: visits === 0 ? '0 com consentimento cookies' : 'PostHog',
    },
    {
      t: 'Por ler',
      v: num(unread),
      s: `${num(s.business?.quotes?.last7d)} orç. · ${num(s.business?.contacts?.last7d)} msg (7d)`,
    },
  ]
    .map(
      (x) =>
        `<div class="card"><div class="card-title">${esc(x.t)}</div><div class="big-num">${esc(x.v)}<span class="sub">${esc(x.s)}</span></div></div>`,
    )
    .join('')

  // Edge hourly chart
  const series = s.cloudflare?.seriesHourly || []
  const ratioEl = document.getElementById('edge-ratio-label')
  if (ratioEl) {
    ratioEl.textContent =
      ratio != null ? `${ratio}% ameaça · ${fmtBytes(s.cloudflare?.bytes24h)}` : 'A carregar série…'
  }
  if (document.getElementById('chart-edge')) {
    edgeChart = upsertChart(edgeChart, 'chart-edge', {
      type: 'line',
      data: {
        labels: series.map((p) => {
          try {
            return new Date(p.t).toLocaleTimeString('pt-PT', { hour: '2-digit' })
          } catch {
            return ''
          }
        }),
        datasets: [
          {
            label: 'Pedidos',
            data: series.map((p) => p.requests),
            borderColor: '#3d8bfd',
            backgroundColor: 'rgba(61,139,253,.1)',
            fill: true,
            tension: 0.35,
            pointRadius: 0,
          },
          {
            label: 'Ameaças',
            data: series.map((p) => p.threats),
            borderColor: '#f87171',
            backgroundColor: 'rgba(248,113,113,.08)',
            fill: true,
            tension: 0.35,
            pointRadius: 0,
          },
        ],
      },
      options: {
        ...chartOpts(true),
        plugins: { legend: { display: true, labels: { color: '#8b9bb0', boxWidth: 10, font: { size: 10 } } } },
      },
    })
  }

  // Funnel + ops rail
  const funnel = document.getElementById('funnel-strip')
  if (funnel) {
    const steps = [
      { l: 'Edge', v: num(edge), ok: edge != null },
      { l: 'Visitas', v: num(visits), ok: visits != null },
      { l: 'Orç. 7d', v: num(s.business?.quotes?.last7d), ok: (s.business?.quotes?.last7d || 0) > 0 },
      { l: 'Inbox', v: num(unread), ok: unread === 0 },
    ]
    funnel.innerHTML = steps
      .map(
        (st, i) =>
          `${i ? '<div class="funnel-arrow">→</div>' : ''}<div class="funnel-step ${st.ok ? 'ok' : 'mute'}"><div class="muted">${esc(st.l)}</div><strong>${esc(st.v)}</strong></div>`,
      )
      .join('')
  }
  const rail = document.getElementById('ops-rail')
  if (rail) {
    rail.innerHTML = `
      <div class="ops-rail-title">Acções rápidas</div>
      <div class="btn-row">
        <button type="button" class="secondary btn-sm" data-action="run-health">Health</button>
        <button type="button" class="secondary btn-sm" data-action="run-verify">Verify prod</button>
        <button type="button" class="ghost-btn btn-sm" id="rail-security">Segurança</button>
        <button type="button" class="ghost-btn btn-sm" id="rail-report">Relatório</button>
      </div>`
    rail.querySelector('#rail-security')?.addEventListener('click', () => switchView('security'))
    rail.querySelector('#rail-report')?.addEventListener('click', () => document.getElementById('export-report-btn')?.click())
  }

  const list = document.getElementById('story-list')
  const items = (story.items?.length ? story.items : (s.recommendations || []).slice(0, 6)).filter(
    (it) => !/Cloudflare sem permissão de analytics/i.test(it.title || '') || s.cloudflare?.requests24h == null,
  )
  if (!items.length) {
    list.innerHTML = empty('Nada urgente', 'Podes respirar — sem acções prioritárias.')
  } else {
    list.innerHTML = items
      .map((it) => {
        const action = it.action || ''
        return `<div class="story-item ${esc(it.severity || 'info')}">
          <strong>${esc(it.title)}</strong>
          <div class="muted">${esc(it.detail || '')}</div>
          <div class="actions">
            <button type="button" class="secondary btn-sm" data-open-playbook="${esc(action)}">Ver o que fazer</button>
            <button type="button" class="ghost-btn btn-sm" data-action="copy-cursor-prompt" data-incident-key="${esc(action)}">Prompt Cursor</button>
          </div>
        </div>`
      })
      .join('')
  }

  const changes = s.changes || []
  document.getElementById('changes-list').innerHTML = changes.length
    ? changes.map((c) => `<div class="change-item">${esc(c.text)}</div>`).join('')
    : empty('Sem deltas', 'À espera da próxima actualização.')

  const dep = document.getElementById('deploy-banner')
  if (s.deployCorrelation) {
    dep.classList.remove('hidden')
    dep.textContent = s.deployCorrelation.message
  } else dep.classList.add('hidden')

  const budget = s.slo?.errorBudgetRemaining
  document.getElementById('slo-target').textContent = `Alvo ${s.slo?.target ?? 99.5}%`
  document.getElementById('slo-panel').innerHTML = `
    <div class="slo-stat"><div class="muted">Uptime</div><div class="big">${s.slo?.uptime30d != null ? esc(s.slo.uptime30d) + '%' : '—'}</div></div>
    <div class="slo-stat"><div class="muted">Error budget</div><div class="big">${budget != null ? esc(budget) + '%' : '—'}
      <div class="budget-bar"><div class="budget-fill ${budget != null && budget < 30 ? 'low' : ''}" style="width:${budget != null ? Math.min(100, budget) : 0}%"></div></div>
    </div></div>
    <div class="slo-stat"><div class="muted">Incidentes abertos</div><div class="big">${esc(s.incidents?.openCount ?? 0)}</div></div>`

  // Saúde comercial
  const edgeN = Number(s.cloudflare?.requests24h) || 0
  const quotes7 = Number(s.business?.quotes?.last7d) || 0
  const unreadN = Number(s.business?.pipeline?.unread_total) || 0
  let commercialTitle = 'Saúde comercial'
  let commercialBody = 'Sem dados de negócio ainda — importa Supabase em Ligações.'
  let commercialTone = 'info'
  if (s.business?.configured) {
    if (edgeN > 500 && quotes7 === 0) {
      commercialTitle = 'Tráfego sem pedidos'
      commercialBody = 'Há carga na edge mas zero orçamentos em 7 dias — testar formulário e Turnstile.'
      commercialTone = 'warning'
    } else if (unreadN > 0) {
      commercialTitle = `${unreadN} por responder`
      commercialBody = `Inbox ${s.business.pipeline?.aging || ''} · ${quotes7} orçamentos / ${num(s.business?.contacts?.last7d)} contactos (7d) · total ${num(s.business?.quotes?.total)}.`
      commercialTone = unreadN > 5 ? 'warning' : 'ok'
    } else {
      commercialTitle = 'Comercial estável'
      commercialBody = `${quotes7} orçamentos (7d) · ${num(s.business?.quotes?.today)} hoje · conversão ${s.conversion?.visitsToQuotes7d != null ? s.conversion.visitsToQuotes7d + '%' : '—'}.`
      commercialTone = 'ok'
    }
  }
  document.getElementById('commercial-health').innerHTML = `
    <h2>Saúde comercial</h2>
    <div class="story-item ${commercialTone}"><strong>${esc(commercialTitle)}</strong><div class="muted">${esc(commercialBody)}</div></div>`

  // Checklist matinal
  const checks = [
    { ok: s.score === 'ok', label: 'Estado geral OK' },
    { ok: s.health?.api?.ok && s.health?.site?.ok && s.health?.db?.ok, label: 'API + loja + BD' },
    { ok: !s.synthetics?.adminExposed, label: 'Admin bloqueado' },
    { ok: s.synthetics?.ok !== false, label: 'Sintéticos OK' },
    { ok: (s.posture?.score ?? 0) >= 80, label: `Postura ≥ 80 (${s.posture?.score ?? '—'})` },
    { ok: unreadN === 0, label: 'Inbox limpo' },
  ]
  document.getElementById('morning-checklist').innerHTML = `
    <h2>Checklist matinal</h2>
    <div class="check-list">${checks
      .map(
        (c) =>
          `<div class="check-row"><div class="check-icon ${c.ok ? 'ok' : 'bad'}">${c.ok ? '✓' : '!'}</div><div>${esc(c.label)}</div></div>`,
      )
      .join('')}</div>`
}

function renderKpis(s) {
  const openInc = s.incidents?.openCount ?? 0
  document.getElementById('kpi-strip').innerHTML = [
    { label: 'Estado', value: (s.score || '—').toUpperCase(), cls: scoreClass(s.score) },
    { label: 'Postura', value: s.posture?.score ?? '—', cls: (s.posture?.score ?? 100) < 70 ? 'warn' : 'ok' },
    { label: 'Incidentes', value: openInc, cls: openInc ? 'warn' : 'ok' },
    { label: 'API ms', value: s.health.api.ms ?? '—', cls: (s.health.api.ms || 0) > 2000 ? 'warn' : 'ok' },
  ]
    .map((k) => `<div class="kpi kpi-${k.cls}"><div class="label">${k.label}</div><div class="value">${esc(k.value)}</div></div>`)
    .join('')

  document.getElementById('score-dot').className = `brand-dot ${scoreClass(s.score)}`
  const ib = document.getElementById('incident-badge')
  ib.textContent = String(openInc)
  ib.classList.toggle('hot', openInc > 0)
  if (s.version) document.getElementById('hub-ver').textContent = `v${s.version}`
}

/* ---------- Analytics ---------- */
function renderAnalytics(s) {
  const b = s.business || {}
  const ph = s.posthog || {}
  const lead = document.getElementById('analytics-lead')
  if (ph.error) lead.textContent = humanOrRaw(ph.error, 'Analytics de visitas com problema — vê Ligações.')
  else if (b.error) lead.textContent = humanOrRaw(b.error, 'Dados de negócio indisponíveis.')
  else if (!b.configured) lead.textContent = 'Importa o .env em Ligações para ver orçamentos e contactos.'
  else {
    lead.textContent = `Negócio via ${b.source === 'api' ? 'API' : 'Supabase'} · edge ${num(s.cloudflare?.requests24h)} pedidos/24h · PostHog ${num(ph.pageviews24h)} visitas/24h`
  }

  document.getElementById('analytics-kpis').innerHTML = [
    { l: 'Edge 24h', v: num(s.cloudflare?.requests24h), h: `${num(s.cloudflare?.threats24h)} ameaças` },
    { l: 'Visitas 24h', v: num(ph.pageviews24h), h: ph.pageviews24h === 0 ? 'Consentimento' : `DAU ${num(ph.dau)}` },
    { l: 'Visitas 30d', v: num(ph.pageviews30d), h: `7d ${num(ph.pageviews7d)}` },
    { l: 'Orçamentos 7d', v: num(b.quotes?.last7d), h: `Total ${num(b.quotes?.total)} · hoje ${num(b.quotes?.today)}` },
  ]
    .map(
      (k) =>
        `<div class="card"><div class="card-title">${esc(k.l)}</div><div class="big-num">${esc(k.v)}<span class="sub">${esc(k.h)}</span></div></div>`,
    )
    .join('')

  const conv = document.getElementById('conversion-cards')
  if (conv) {
    const edgeN = Number(s.cloudflare?.requests24h) || 0
    const pv7 = Number(ph.pageviews7d ?? ph.pageviews24h) || 0
    const q7 = Number(b.quotes?.last7d) || 0
    const rate = s.conversion?.visitsToQuotes7d
    conv.innerHTML = [
      {
        l: 'Conversão visitas→orç.',
        v: rate != null ? `${rate}%` : '—',
        h: pv7 ? `${q7} orç. / ${pv7} visitas (7d)` : 'Sem visitas PostHog',
      },
      {
        l: 'Edge vs analytics',
        v: edgeN && ph.pageviews24h != null ? `${Math.round((Number(ph.pageviews24h) / edgeN) * 1000) / 10}%` : '—',
        h: 'Visitas consentidas / pedidos edge',
      },
      {
        l: 'Logs API 24h',
        v: num(s.axiom?.eventCount24h),
        h: s.axiom?.error ? 'Axiom com problema' : 'Eventos no dataset',
      },
    ]
      .map(
        (k) =>
          `<div class="card accent-card"><div class="card-title">${esc(k.l)}</div><div class="big-num">${esc(k.v)}<span class="sub">${esc(k.h)}</span></div></div>`,
      )
      .join('')
  }

  const hourly = ph.hourly || []
  visitsChart = upsertChart(visitsChart, 'chart-visits', {
    type: 'bar',
    data: {
      labels: hourly.map((h) => h.label || ''),
      datasets: [{ data: hourly.map((h) => (typeof h === 'object' ? h.count : h)), backgroundColor: 'rgba(61,139,253,.55)', label: 'PV' }],
    },
    options: chartOpts(false),
  })

  const daily = ph.daily || []
  dailyChart = upsertChart(dailyChart, 'chart-daily', {
    type: 'line',
    data: {
      labels: daily.map((d) => {
        try {
          return new Date(d.day).toLocaleDateString('pt-PT', { day: '2-digit', month: '2-digit' })
        } catch {
          return ''
        }
      }),
      datasets: [
        {
          data: daily.map((d) => d.count),
          borderColor: '#3dd68c',
          backgroundColor: 'rgba(61,214,140,.12)',
          fill: true,
          tension: 0.3,
          pointRadius: 2,
        },
      ],
    },
    options: chartOpts(false),
  })

  businessChart = upsertChart(businessChart, 'chart-business', {
    type: 'bar',
    data: {
      labels: ['Orçamentos', 'Contactos', 'Encomendas'],
      datasets: [
        {
          data: [b.quotes?.last7d || 0, b.contacts?.last7d || 0, b.orders?.last7d || 0],
          backgroundColor: ['rgba(61,211,140,.55)', 'rgba(245,158,11,.55)', 'rgba(61,139,253,.55)'],
        },
      ],
    },
    options: chartOpts(false),
  })

  const pages = ph.topPages || []
  document.getElementById('top-pages').innerHTML = pages.length
    ? `<table class="data"><thead><tr><th>Rota</th><th>Views</th></tr></thead><tbody>${pages
        .map((p) => `<tr><td>${esc(p.path)}</td><td>${esc(p.views)}</td></tr>`)
        .join('')}</tbody></table>`
    : empty('Sem páginas', 'Sem pageviews PostHog nos últimos 7 dias (ou sem consentimento).')

  const insights = [
    ...(s.baselines?.insights || []).map((i) => ({
      title: i.title,
      text: i.detail,
      value: i.delta != null ? `${i.delta}%` : '·',
      action: i.action,
    })),
    {
      title: 'Inbox',
      text: `${b.pipeline?.unread_total ?? 0} por ler (${b.pipeline?.aging || '—'}).`,
      value: b.pipeline?.unread_total ?? 0,
      action: 'business-unread',
    },
    {
      title: 'Totais',
      text: `${num(b.quotes?.total)} orçamentos · ${num(b.contacts?.total)} contactos · ${num(b.orders?.total)} encomendas.`,
      value: 'Σ',
    },
  ]
  document.getElementById('analytics-insights').innerHTML = insights
    .map(
      (row) =>
        `<div class="insight-row" ${row.action ? `data-open-playbook="${esc(row.action)}" style="cursor:pointer"` : ''}>
          <div><strong>${esc(row.title)}</strong><span class="muted"> ${esc(row.text)}</span></div>
          <strong>${esc(row.value)}</strong>
        </div>`,
    )
    .join('')
}

function humanOrRaw(err, fallback) {
  if (!err) return fallback
  if (/403|query|token/i.test(err) && /axiom/i.test(err)) return 'Registo de erros sem permissão de leitura — actualiza o token Axiom.'
  if (/403|Query/i.test(err) && /posthog|phx|phc/i.test(err)) return 'PostHog: usa chave pessoal phx_ com Query:Read.'
  if (err.length > 120) return fallback
  return err
}

/* ---------- Security ---------- */
function renderSecurity(s) {
  const posture = s.posture || { score: null, checks: [] }
  const syn = s.synthetics || { steps: [] }
  const waf = s.cloudflare?.waf || {}

  document.getElementById('security-kpis').innerHTML = [
    { l: 'Postura', v: posture.score != null ? `${posture.score}/100` : '—', h: 'Checks ponderados' },
    { l: 'Sintéticos', v: syn.ok == null ? '—' : syn.ok ? 'OK' : 'Falha', h: 'Jornadas HTTP' },
    { l: 'Bloqueios 24h', v: num(s.cloudflare?.threats24h), h: s.cloudflare?.threatRatio != null ? `${s.cloudflare.threatRatio}% do tráfego` : 'WAF / ameaças' },
  ]
    .map(
      (k) =>
        `<div class="card"><div class="card-title">${esc(k.l)}</div><div class="big-num">${esc(k.v)}<span class="sub">${esc(k.h)}</span></div></div>`,
    )
    .join('')

  const threatBox = document.getElementById('threat-breakdown')
  if (threatBox) {
    const countries = waf.topCountries || []
    threatBox.innerHTML = [
      `<div class="card"><div class="card-title">Pedidos 24h</div><div class="big-num">${esc(num(s.cloudflare?.requests24h))}<span class="sub">${esc(fmtBytes(s.cloudflare?.bytes24h))}</span></div></div>`,
      `<div class="card"><div class="card-title">Ameaças</div><div class="big-num">${esc(num(s.cloudflare?.threats24h))}<span class="sub">Taxa ${esc(num(s.cloudflare?.threatRatio))}%</span></div></div>`,
      `<div class="card"><div class="card-title">Top países</div><div class="country-chips">${
        countries.length
          ? countries
              .slice(0, 5)
              .map((c) => `<span class="chip">${esc(c.country)} <strong>${esc(c.count)}</strong></span>`)
              .join('')
          : '<span class="muted">Sem breakdown</span>'
      }</div></div>`,
    ].join('')
  }

  document.getElementById('posture-checks').innerHTML =
    (posture.checks || [])
      .map(
        (c) =>
          `<div class="check-row"><div class="check-icon ${c.ok ? 'ok' : 'bad'}">${c.ok ? '✓' : '!'}</div><div>${esc(c.label)}${c.detail ? `<div class="muted">${esc(c.detail)}</div>` : ''}</div><span class="muted">×${esc(c.weight)}</span></div>`,
      )
      .join('') || empty('—', 'Sem checks')

  document.getElementById('synth-steps').innerHTML =
    (syn.steps || [])
      .map(
        (c) =>
          `<div class="check-row"><div class="check-icon ${c.ok ? 'ok' : 'bad'}">${c.ok ? '✓' : '!'}</div><div>${esc(c.label)}<div class="muted">${esc(c.detail || '')}</div></div><span class="muted">${esc(c.ms)} ms</span></div>`,
      )
      .join('') || empty('A correr…', 'Na próxima actualização')

  const paths = waf.topPaths || []
  document.getElementById('waf-panel').innerHTML = paths.length
    ? `<table class="data"><thead><tr><th>Path</th><th>Acção</th><th>N</th></tr></thead><tbody>${paths
        .map(
          (p) =>
            `<tr><td>${esc(p.path)}</td><td>${esc(p.action || '—')}</td><td>${esc(p.count)}</td></tr>`,
        )
        .join('')}</tbody></table>`
    : empty(
        waf.limited || s.cloudflare?.wafError ? 'Feed WAF limitado' : 'Sem eventos path',
        waf.limited || s.cloudflare?.wafError
          ? `${num(s.cloudflare?.threats24h)} ameaças agregadas via Analytics. Para paths detalhados: Zone → Firewall Services → Read no token.`
          : 'Nenhum agrupamento de path nas últimas 24h (bom sinal).',
      )

  const events = waf.recentEvents || []
  document.getElementById('waf-events').innerHTML = events.length
    ? events
        .slice(0, 10)
        .map(
          (e) =>
            `<div class="change-item"><strong>${esc(e.action)}</strong> ${esc(e.path)} · ${esc(e.country)} <span class="muted">${fmtTime(e.at)}</span></div>`,
        )
        .join('')
    : empty(
        'Sem feed de eventos',
        s.cloudflare?.threats24h
          ? `Há ${num(s.cloudflare.threats24h)} ameaças no agregado — o feed por evento precisa Firewall Services Read.`
          : 'Sem eventos recentes.',
      )

  document.getElementById('security-tech').textContent = [
    s.cloudflare?.analyticsError ? `CF analytics: ${s.cloudflare.analyticsError}` : null,
    s.cloudflare?.wafError ? `CF WAF: ${s.cloudflare.wafError}` : null,
    s.axiom?.error ? `Axiom: ${s.axiom.error}` : null,
    `Zone: ${s.cloudflare?.zoneName || '—'} (${s.cloudflare?.zoneStatus || '—'})`,
    `Edge: ${num(s.cloudflare?.requests24h)} req · ${num(s.cloudflare?.threats24h)} thr`,
  ]
    .filter(Boolean)
    .join('\n')
}

/* ---------- Incidents ---------- */
function renderIncidents(s) {
  const open = s.incidents?.open || []
  const closed = s.incidents?.closed || []
  document.getElementById('incident-kpis').innerHTML = [
    { l: 'Abertos', v: open.length },
    { l: 'MTTR médio', v: fmtDuration(s.incidents?.mttrAvgMs) },
    { l: 'Resolvidos', v: closed.length },
  ]
    .map((k) => `<div class="card"><div class="card-title">${esc(k.l)}</div><div class="big-num">${esc(k.v)}</div></div>`)
    .join('')

  document.getElementById('incident-open').innerHTML = open.length
    ? open
        .map(
          (i) => `<div class="incident-card ${esc(i.severity || 'warning')}">
        <div><strong>${esc(i.title)}</strong><div class="muted">${esc(i.detail || '')}</div></div>
        <div class="incident-meta">${pill(i.status || 'open', 'warn')}<span>${fmtTime(i.openedAt)}</span></div>
        <div class="btn-row" style="margin:0">
          <button type="button" class="secondary btn-sm" data-open-playbook="${esc(i.action || '')}" data-incident-key="${esc(i.key)}">Playbook</button>
          <button type="button" class="ghost-btn btn-sm" data-ack="${esc(i.key)}">Ack</button>
          <button type="button" class="ghost-btn btn-sm btn-ok" data-resolve="${esc(i.key)}">Resolver</button>
          <button type="button" class="ghost-btn btn-sm" data-action="copy-cursor-prompt" data-incident-key="${esc(i.key)}">Prompt</button>
        </div>
      </div>`,
        )
        .join('')
    : empty('Zero abertos', 'Nenhum incidente activo.')

  document.getElementById('incident-closed').innerHTML = closed.length
    ? closed
        .slice(0, 15)
        .map(
          (i) =>
            `<div class="incident-card" style="border-left-color:var(--accent)"><strong>${esc(i.title)}</strong><div class="muted">MTTR ${fmtDuration(i.mttrMs)} · ${fmtTime(i.resolvedAt)}</div></div>`,
        )
        .join('')
    : empty('Histórico vazio', 'Resolvidos aparecem aqui.')

  const feed = document.getElementById('alert-feed')
  if (!s.alerts?.length) feed.innerHTML = empty('Feed limpo', 'Sem alertas activos.')
  else {
    feed.innerHTML = s.alerts
      .map(
        (a) =>
          `<div class="alert-item ${esc(a.severity || 'info')}${a.url ? ' has-link' : ''}" data-url="${esc(a.url || '')}">
        <div class="alert-src">${esc(a.source)}</div>
        <div><strong>${esc(a.title)}</strong><br><span class="muted">${esc(a.message || '')}</span></div>
        <div class="muted">${fmtTime(a.ts)}</div>
      </div>`,
      )
      .join('')
  }
}

/* ---------- Infra / CI ---------- */
function renderInfra(s) {
  document.getElementById('health-cards').innerHTML = [
    { t: 'API', ok: s.health.api.ok, d: `${s.health.api.ms ?? '—'} ms · v${s.health.api.version || '?'}` },
    { t: 'BD', ok: s.health.db.ok, d: `${s.health.db.ms ?? '—'} ms` },
    { t: 'Loja', ok: s.health.site.ok, d: `${s.health.site.ms ?? '—'} ms` },
  ]
    .map(
      (c) =>
        `<div class="card"><div class="card-head"><span class="card-title">${esc(c.t)}</span>${pill(c.ok ? 'OK' : 'FALHA', c.ok ? 'ok' : 'bad')}</div><div class="muted">${esc(c.d)}</div></div>`,
    )
    .join('')

  const lat = s.metrics?.latencyHistory || []
  latencyChart = upsertChart(latencyChart, 'chart-latency', {
    type: 'line',
    data: {
      labels: lat.map((p) => new Date(p.t).toLocaleTimeString('pt-PT', { hour: '2-digit', minute: '2-digit' })),
      datasets: [
        {
          data: lat.map((p) => p.ms),
          borderColor: '#3d8bfd',
          backgroundColor: 'rgba(61,139,253,.12)',
          fill: true,
          tension: 0.3,
          pointRadius: 0,
        },
      ],
    },
    options: chartOpts(false),
  })

  const hint = document.getElementById('errors-hint')
  if (s.axiom?.error) hint.textContent = humanOrRaw(s.axiom.error, 'Registo de erros indisponível')
  else hint.textContent = 'Axiom · erros por hora'

  const err = s.metrics?.errorTrend || []
  errorsChart = upsertChart(errorsChart, 'chart-errors', {
    type: 'bar',
    data: {
      labels: err.map((e) => {
        try {
          return new Date(e.hour).toLocaleTimeString('pt-PT', { hour: '2-digit' })
        } catch {
          return ''
        }
      }),
      datasets: [{ data: err.map((e) => e.count), backgroundColor: 'rgba(248,113,113,.55)' }],
    },
    options: chartOpts(false),
  })

  const up = s.uptime
  document.getElementById('uptime-table').innerHTML =
    up?.monitors?.length
      ? `<table class="data"><thead><tr><th>Monitor</th><th>Estado</th><th>ms</th></tr></thead><tbody>${up.monitors
          .map(
            (m) =>
              `<tr class="${m.url ? 'clickable' : ''}" data-url="${esc(m.url || '')}"><td>${esc(m.name)}</td><td>${pill(m.statusLabel, m.status === 2 ? 'ok' : 'bad')}</td><td>${esc(m.avgResponse ?? '—')}</td></tr>`,
          )
          .join('')}</tbody></table>`
      : empty('Sem monitores', '—')

  document.getElementById('edge-metrics').innerHTML = [
    ['Zona', s.cloudflare?.zoneName || '—'],
    ['Pedidos 24h', num(s.cloudflare?.requests24h)],
    ['Ameaças 24h', num(s.cloudflare?.threats24h)],
    ['Taxa ameaça', s.cloudflare?.threatRatio != null ? `${s.cloudflare.threatRatio}%` : '—'],
    ['Bytes', fmtBytes(s.cloudflare?.bytes24h)],
    ['Pageviews 24h', num(s.posthog?.pageviews24h)],
    ['Logs Axiom 24h', num(s.axiom?.eventCount24h)],
  ]
    .map(([k, v]) => `<div class="metric-row"><span>${esc(k)}</span><strong>${esc(v)}</strong></div>`)
    .join('')

  const st = document.getElementById('sentry-table')
  if (!s.sentry?.configured) st.innerHTML = empty('Sentry', 'Token em falta — Ligações.')
  else if (s.sentry.error) st.innerHTML = empty('Sentry', humanOrRaw(s.sentry.error, 'Erro'))
  else if (!s.sentry.issues?.length) st.innerHTML = empty('Limpo', 'Sem issues abertos.')
  else {
    st.innerHTML = `<table class="data"><thead><tr><th>Erro</th><th>Nível</th><th>Count</th><th>Último</th></tr></thead><tbody>${s.sentry.issues
      .map((i) => {
        const ageMs = i.lastSeen ? Date.now() - new Date(i.lastSeen).getTime() : null
        const age =
          ageMs == null
            ? '—'
            : ageMs < 86400000
              ? 'hoje'
              : ageMs < 7 * 86400000
                ? `${Math.round(ageMs / 86400000)}d`
                : `${Math.round(ageMs / (7 * 86400000))}sem`
        const stale = ageMs != null && ageMs > 7 * 86400000
        return `<tr class="${i.permalink ? 'clickable' : ''}${stale ? ' muted-row' : ''}" data-url="${esc(i.permalink || '')}"><td>${esc(i.title)}</td><td>${esc(i.level)}</td><td>${esc(i.count)}</td><td>${esc(age)}</td></tr>`
      })
      .join('')}</tbody></table>
      <p class="panel-hint" style="margin-top:10px">Issues com +7 dias sem eventos são ruído antigo — resolve em lote no Sentry (token do hub é só leitura).</p>`
  }

  const ugh = document.getElementById('uptime-gh-table')
  if (!s.uptimeGh?.configured) ugh.innerHTML = empty('GitHub', 'Liga GitHub')
  else if (!s.uptimeGh.runs?.length) ugh.innerHTML = empty('Sem runs', '—')
  else {
    ugh.innerHTML = `<table class="data"><thead><tr><th>Run</th><th>Estado</th><th>Quando</th></tr></thead><tbody>${s.uptimeGh.runs
      .map((r) => {
        const kind = r.conclusion === 'success' ? 'ok' : r.conclusion === 'failure' ? 'bad' : 'warn'
        return `<tr class="clickable" data-url="${esc(r.html_url || r.url || '')}"><td>${esc(r.name)}</td><td>${pill(r.conclusion || r.status, kind)}</td><td>${fmtTime(r.createdAt)}</td></tr>`
      })
      .join('')}</tbody></table>`
  }
}

function renderCi(s) {
  const rel = document.getElementById('release-card')
  if (s.release) {
    rel.innerHTML = `<h2>Último release</h2><p><strong>${esc(s.release.tag)}</strong> — ${esc(s.release.name || '')}</p><p class="muted">${fmtTime(s.release.publishedAt)}</p>${
      s.release.html_url || s.release.url
        ? `<button type="button" class="ghost-btn btn-sm" data-url="${esc(s.release.html_url || s.release.url)}">Abrir</button>`
        : ''
    }`
  } else rel.innerHTML = '<h2>Release</h2>' + empty('—', 'Liga GitHub')

  const el = document.getElementById('ci-table')
  if (!s.ci?.configured) el.innerHTML = empty('CI', 'Liga GitHub')
  else if (!s.ci.runs?.length) el.innerHTML = empty('Sem runs', '—')
  else {
    el.innerHTML = `<table class="data"><thead><tr><th>Workflow</th><th>Branch</th><th>Estado</th><th>Quando</th></tr></thead><tbody>${s.ci.runs
      .map((r) => {
        const kind = r.conclusion === 'success' ? 'ok' : r.conclusion === 'failure' ? 'bad' : 'warn'
        return `<tr class="clickable" data-url="${esc(r.html_url || r.url || '')}"><td>${esc(r.name)}</td><td>${esc(r.branch)}</td><td>${pill(r.conclusion || r.status, kind)}</td><td>${fmtTime(r.createdAt)}</td></tr>`
      })
      .join('')}</tbody></table>`
  }
}

function chartOpts(legend) {
  return {
    responsive: true,
    plugins: { legend: { display: legend } },
    scales: {
      x: { ticks: { color: '#8b9bb0', maxTicksLimit: 10 }, grid: { color: '#243041' } },
      y: { ticks: { color: '#8b9bb0', precision: 0 }, grid: { color: '#243041' }, beginAtZero: true },
    },
  }
}

function upsertChart(ref, id, cfg) {
  const ctx = document.getElementById(id)
  if (!ctx || typeof Chart === 'undefined') return ref
  if (ref) {
    ref.data = cfg.data
    ref.options = { ...ref.options, ...cfg.options }
    ref.update('none')
    return ref
  }
  return new Chart(ctx, cfg)
}

function renderAll(s) {
  snapshot = s
  lastUpdate = Date.now()
  document.getElementById('live-indicator').textContent = `● ${new Date().toLocaleTimeString('pt-PT')}`
  document.getElementById('live-indicator').classList.remove('stale')
  renderKpis(s)
  renderTower(s)
  renderAnalytics(s)
  renderSecurity(s)
  renderIncidents(s)
  renderInfra(s)
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
  const el = document.getElementById(`view-${name}`)
  if (!el) return
  el.classList.add('active')
  document.getElementById('view-title').textContent = views[name].title
  document.getElementById('view-sub').textContent = views[name].sub
  if (name === 'setup') renderIntegrations()
  closePalette()
}

document.querySelectorAll('.nav-btn').forEach((btn) => {
  btn.addEventListener('click', () => switchView(btn.dataset.view))
})

/* Drawer / playbook */
function openDrawer(action, incidentKey) {
  const incident =
    (snapshot?.incidents?.open || []).find((i) => i.key === incidentKey) ||
    (snapshot?.recommendations || []).find((r) => r.action === action) ||
    (snapshot?.story?.items || []).find((i) => i.action === action) ||
    { action, title: action, key: incidentKey || action }
  selectedIncident = incident
  window.hub.getPlaybook(action || incident.action).then((res) => {
    const pb = res.playbook || { title: 'Playbook', steps: [], actions: [] }
    document.getElementById('drawer-title').textContent = pb.title || incident.title || 'Playbook'
    document.getElementById('drawer-detail').textContent = incident.detail || ''
    document.getElementById('drawer-steps').innerHTML = (pb.steps || []).map((st) => `<li>${esc(st)}</li>`).join('')
    document.getElementById('drawer-actions').innerHTML = (pb.actions || [])
      .map(
        (id) =>
          `<button type="button" class="ghost-btn btn-sm" data-action="${esc(id)}" data-incident-key="${esc(incident.key || action)}">${esc(ACTION_LABELS[id] || id)}</button>`,
      )
      .join('')
    const dr = document.getElementById('drawer')
    dr.classList.remove('hidden')
    dr.setAttribute('aria-hidden', 'false')
  })
}

document.getElementById('drawer-close').addEventListener('click', () => {
  document.getElementById('drawer').classList.add('hidden')
})

/* Command palette */
const PALETTE_CMDS = [
  { id: 'overview', label: 'Ir para Visão geral', run: () => switchView('overview') },
  { id: 'analytics', label: 'Ir para Analytics', run: () => switchView('analytics') },
  { id: 'security', label: 'Ir para Segurança', run: () => switchView('security') },
  { id: 'alerts', label: 'Ir para Incidentes', run: () => switchView('alerts') },
  { id: 'metrics', label: 'Ir para Infra', run: () => switchView('metrics') },
  { id: 'cicd', label: 'Ir para CI/CD', run: () => switchView('cicd') },
  { id: 'setup', label: 'Ir para Ligações', run: () => switchView('setup') },
  {
    id: 'health',
    label: 'Correr health + sintéticos',
    hint: 'Probes',
    run: async () => {
      toast('A correr…')
      const res = await window.hub.runAction('run-health', {})
      if (res?.snapshot) renderAll(res.snapshot)
      toast(res?.ok ? 'Health OK' : 'Com falhas — vê Segurança')
    },
  },
  {
    id: 'report',
    label: 'Exportar relatório mensal',
    run: async () => {
      const res = await window.hub.exportReport()
      toast(res?.ok ? `Guardado: ${res.path}` : 'Falhou')
    },
  },
  {
    id: 'refresh',
    label: 'Actualizar agora',
    run: async () => {
      renderAll(await window.hub.refreshNow())
      toast('Actualizado')
    },
  },
]

function openPalette() {
  document.getElementById('palette').classList.remove('hidden')
  document.getElementById('palette-backdrop').classList.remove('hidden')
  const input = document.getElementById('palette-input')
  input.value = ''
  renderPalette('')
  input.focus()
}

function closePalette() {
  document.getElementById('palette').classList.add('hidden')
  document.getElementById('palette-backdrop').classList.add('hidden')
}

function renderPalette(q) {
  const qq = q.toLowerCase().trim()
  const list = PALETTE_CMDS.filter((c) => !qq || c.label.toLowerCase().includes(qq) || c.id.includes(qq))
  document.getElementById('palette-results').innerHTML = list
    .map(
      (c, i) =>
        `<div class="palette-item ${i === 0 ? 'active' : ''}" data-cmd="${esc(c.id)}">${esc(c.label)}${c.hint ? `<div class="hint">${esc(c.hint)}</div>` : ''}</div>`,
    )
    .join('')
}

document.getElementById('palette-btn').addEventListener('click', openPalette)
document.getElementById('palette-backdrop').addEventListener('click', closePalette)
document.getElementById('palette-input').addEventListener('input', (e) => renderPalette(e.target.value))
document.getElementById('palette-input').addEventListener('keydown', (e) => {
  if (e.key === 'Escape') closePalette()
  if (e.key === 'Enter') {
    const first = document.querySelector('.palette-item')
    if (first) {
      const cmd = PALETTE_CMDS.find((c) => c.id === first.dataset.cmd)
      cmd?.run()
      closePalette()
    }
  }
})
document.getElementById('palette-results').addEventListener('click', (e) => {
  const item = e.target.closest('[data-cmd]')
  if (!item) return
  PALETTE_CMDS.find((c) => c.id === item.dataset.cmd)?.run()
  closePalette()
})

document.addEventListener('keydown', (e) => {
  if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === 'k') {
    e.preventDefault()
    openPalette()
  }
  if (e.key === 'Escape') {
    closePalette()
    document.getElementById('drawer').classList.add('hidden')
  }
})

document.getElementById('refresh-btn').addEventListener('click', async () => {
  renderAll(await window.hub.refreshNow())
  toast('Actualizado')
})

document.getElementById('export-report-btn').addEventListener('click', async () => {
  const res = await window.hub.exportReport()
  toast(res?.ok ? `Relatório: ${res.path}` : 'Falhou export')
})

document.getElementById('btn-run-health').addEventListener('click', async () => {
  toast('A correr sintéticos…')
  const res = await window.hub.runAction('run-health', {})
  if (res?.snapshot) renderAll(res.snapshot)
  toast(res?.ok ? 'OK' : 'Falhas — vê passos')
})

document.getElementById('btn-import-env').addEventListener('click', async () => {
  await window.hub.importEnv()
  await renderIntegrations()
  renderAll(await window.hub.refreshNow())
  toast('Credenciais importadas')
})

document.getElementById('btn-open-config').addEventListener('click', () => window.hub.openConfigFile())
document.getElementById('btn-gh-cli').addEventListener('click', async () => {
  const r = await window.hub.githubTryGhCli()
  toast(r.ok ? 'GitHub ligado' : 'CLI não detectado')
  if (r.ok) await renderIntegrations()
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
  box.innerHTML = `Abre <a href="#" id="gh-verif-link">${esc(flow.verificationUri)}</a><br>Código: <strong style="font-size:1.3rem">${esc(flow.userCode)}</strong>`
  document.getElementById('gh-verif-link')?.addEventListener('click', (e) => {
    e.preventDefault()
    openUrl(flow.verificationUri)
  })
  const res = await window.hub.githubPollDevice({
    clientId: flow.clientId,
    deviceCode: flow.deviceCode,
    interval: flow.interval,
  })
  box.textContent = res.ok ? 'GitHub ligado.' : res.error || 'Falhou'
  if (res.ok) await renderIntegrations()
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
  toast('Guardado')
})

document.getElementById('gh-cli-link').addEventListener('click', (e) => {
  e.preventDefault()
  openUrl('https://cli.github.com/')
})

document.body.addEventListener('click', async (e) => {
  const urlEl = e.target.closest('[data-url]')
  if (urlEl?.dataset.url) {
    openUrl(urlEl.dataset.url)
    return
  }
  const pb = e.target.closest('[data-open-playbook]')
  if (pb) {
    openDrawer(pb.dataset.openPlaybook, pb.dataset.incidentKey)
    return
  }
  const ack = e.target.closest('[data-ack]')
  if (ack) {
    const res = await window.hub.incidentAck(ack.dataset.ack)
    if (res?.snapshot) renderAll(res.snapshot)
    toast('Acknowledged')
    return
  }
  const resolveBtn = e.target.closest('[data-resolve]')
  if (resolveBtn) {
    const res = await window.hub.incidentResolve(resolveBtn.dataset.resolve)
    if (res?.snapshot) renderAll(res.snapshot)
    toast('Resolvido')
    return
  }
  const act = e.target.closest('[data-action]')
  if (act) await handleAction(act.dataset.action, act.dataset.incidentKey)
})

async function handleAction(actionId, incidentKey) {
  const incident =
    selectedIncident ||
    (snapshot?.incidents?.open || []).find((i) => i.key === incidentKey) ||
    { action: incidentKey, title: incidentKey, key: incidentKey }

  if (actionId === 'copy-cursor-prompt') {
    const res = await window.hub.copyPrompt(incident, snapshot)
    toast(res?.ok ? `Prompt copiado (${res.chars})` : 'Falhou')
    return
  }
  if (actionId === 'open-path') {
    const file = incident.file || (await window.hub.getPlaybook(incident.action)).playbook?.file
    const res = await window.hub.runAction('open-path', { file, path: file })
    toast(res?.ok ? 'Aberto' : res?.error || 'Sem ficheiro')
    return
  }
  if (actionId === 'sentry-resolve') {
    const issueId = incident.issueId || snapshot?.sentry?.issues?.[0]?.id
    if (!issueId) {
      toast('Sem issue')
      return
    }
    const res = await window.hub.runAction('sentry-resolve', { issueId })
    toast(res?.ok ? 'Resolvido no Sentry' : res?.error || 'Falhou')
    if (res?.ok) renderAll(await window.hub.refreshNow())
    return
  }
  toast(`A executar ${ACTION_LABELS[actionId] || actionId}…`)
  const log = document.getElementById('action-log')
  const pre = document.getElementById('action-log-pre')
  log.classList.remove('hidden')
  pre.textContent = '…'
  const res = await window.hub.runAction(actionId, { incident, snapshot })
  pre.textContent = res?.stdout || res?.stderr || JSON.stringify(res, null, 2)
  if (res?.snapshot) renderAll(res.snapshot)
  toast(res?.ok ? 'Concluído' : res?.error || 'Com erros')
  setTimeout(() => log.classList.add('hidden'), 10000)
}

window.hub.onSnapshot(renderAll)
window.hub.onSnapshotError((msg) => {
  document.getElementById('live-indicator').textContent = `● Erro de actualização`
  document.getElementById('live-indicator').classList.add('stale')
  console.warn(msg)
})

setInterval(() => {
  if (lastUpdate && Date.now() - lastUpdate > 90000) {
    document.getElementById('live-indicator').classList.add('stale')
  }
}, 10000)

renderIntegrations()
