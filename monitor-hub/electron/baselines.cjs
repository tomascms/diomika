/**
 * Baselines vs média recente — anomalias de tráfego/negócio.
 */

function avg(arr) {
  const nums = (arr || []).filter((n) => typeof n === 'number' && !Number.isNaN(n))
  if (!nums.length) return null
  return nums.reduce((a, b) => a + b, 0) / nums.length
}

function pctDelta(current, baseline) {
  if (baseline == null || baseline === 0) {
    if (current == null) return null
    if (current === 0) return 0
    return null
  }
  return Math.round(((current - baseline) / baseline) * 100)
}

function computeBaselines(snapshot, history) {
  // history: optional ring of past pageviews24h / quotes7d samples from hub-metrics-history
  const hist = history || {}
  const pvHist = hist.pageviews24h || []
  const quotesHist = hist.quotes7d || []

  const pageviews24h = snapshot.posthog?.pageviews24h
  const requests24h = snapshot.cloudflare?.requests24h
  const quotes7d = snapshot.business?.quotes?.last7d
  const contacts7d = snapshot.business?.contacts?.last7d

  const pvAvg = avg(pvHist.slice(-7))
  const quotesAvg = avg(quotesHist.slice(-7))

  const insights = []

  const pvDelta = pctDelta(pageviews24h, pvAvg)
  if (pvDelta != null && pvAvg != null && pvAvg > 5 && pvDelta <= -50) {
    insights.push({
      id: 'analytics-drop',
      severity: 'warning',
      title: 'Queda de visitas',
      detail: `Pageviews 24h ${pageviews24h} vs média recente ${Math.round(pvAvg)} (${pvDelta}%).`,
      action: 'analytics-drop',
      delta: pvDelta,
    })
  }
  if (pvDelta != null && pvAvg != null && pvAvg > 0 && pvDelta >= 100) {
    insights.push({
      id: 'traffic-spike',
      severity: 'info',
      title: 'Pico de tráfego',
      detail: `Pageviews 24h ${pageviews24h} vs média ${Math.round(pvAvg)} (+${pvDelta}%).`,
      action: null,
      delta: pvDelta,
    })
  }

  const edge = Number(requests24h) || 0
  const quotes = Number(quotes7d) || 0
  if (edge > 500 && quotes === 0 && snapshot.business?.configured) {
    insights.push({
      id: 'business-stall',
      severity: 'warning',
      title: 'Tráfego sem orçamentos',
      detail: `${edge} pedidos edge / 0 orçamentos (7d) — testar formulário e Turnstile.`,
      action: 'business-stall',
    })
  }

  const unread = snapshot.business?.pipeline?.unread_total ?? 0
  if (unread > 0) {
    insights.push({
      id: 'business-unread',
      severity: unread > 5 ? 'warning' : 'info',
      title: `${unread} por ler no inbox`,
      detail: 'Orçamentos e mensagens à espera no backoffice.',
      action: 'business-unread',
    })
  }

  return {
    pageviews: {
      current: pageviews24h ?? null,
      avg7: pvAvg != null ? Math.round(pvAvg) : null,
      deltaPct: pvDelta,
    },
    quotes: {
      current: quotes7d ?? null,
      avg7: quotesAvg != null ? Math.round(quotesAvg) : null,
      deltaPct: pctDelta(quotes7d, quotesAvg),
    },
    contacts7d: contacts7d ?? null,
    edgeRequests24h: requests24h ?? null,
    insights,
  }
}

function pushBaselineSample(history, snapshot) {
  const next = {
    pageviews24h: [...(history.pageviews24h || [])],
    quotes7d: [...(history.quotes7d || [])],
  }
  if (typeof snapshot.posthog?.pageviews24h === 'number') {
    next.pageviews24h.push(snapshot.posthog.pageviews24h)
    if (next.pageviews24h.length > 14) next.pageviews24h.shift()
  }
  if (typeof snapshot.business?.quotes?.last7d === 'number') {
    next.quotes7d.push(snapshot.business.quotes.last7d)
    if (next.quotes7d.length > 14) next.quotes7d.shift()
  }
  return next
}

module.exports = { computeBaselines, pushBaselineSample, pctDelta, avg }
