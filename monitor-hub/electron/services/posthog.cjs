const { fetchJson } = require('./http.cjs')

function apiBase(host) {
  let base = (host || 'https://eu.posthog.com').replace(/\/$/, '')
  if (base.includes('eu.i.posthog.com')) base = 'https://eu.posthog.com'
  if (base.includes('us.i.posthog.com')) base = 'https://us.posthog.com'
  return base
}

async function hogqlQuery(base, pid, apiKey, query) {
  return fetchJson(`${base}/api/projects/${pid}/query/`, {
    method: 'POST',
    headers: {
      Authorization: `Bearer ${apiKey}`,
      Accept: 'application/json',
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({ query: { kind: 'HogQLQuery', query } }),
  })
}

function hogqlNumber(data) {
  const row = data?.results?.[0]
  if (Array.isArray(row)) return Number(row[0]) || 0
  if (row && typeof row === 'object') {
    const val = Object.values(row)[0]
    return Number(val) || 0
  }
  return 0
}

function fillHourlyBuckets(rows) {
  // rows: [{hour: Date|string, count}]
  const map = new Map()
  for (const r of rows) {
    const d = new Date(r.hour)
    if (Number.isNaN(d.getTime())) continue
    const key = d.toISOString().slice(0, 13)
    map.set(key, (map.get(key) || 0) + r.count)
  }
  const out = []
  const now = new Date()
  now.setMinutes(0, 0, 0)
  for (let i = 23; i >= 0; i--) {
    const t = new Date(now.getTime() - i * 3600 * 1000)
    const key = t.toISOString().slice(0, 13)
    out.push({ hour: t.toISOString(), count: map.get(key) || 0, label: `${t.getHours()}h` })
  }
  return out
}

async function fetchPosthog(cfg) {
  const { apiKey, projectId, host } = cfg.posthog || {}
  if (!apiKey || !projectId) {
    return { configured: false, dau: null, pageviews24h: null, pageviews7d: null, hourly: [], topPages: [], funnel: null }
  }
  // Reject project API keys for Query API
  if (String(apiKey).startsWith('phc_')) {
    return {
      configured: true,
      error: 'Chave de projecto (phc_) não serve para o hub — usa Personal API Key phx_ com Query:Read',
      dau: null,
      pageviews24h: null,
      pageviews7d: null,
      hourly: [],
      topPages: [],
      funnel: null,
    }
  }

  const base = apiBase(host)
  const pid = String(projectId)
  const headers = { Authorization: `Bearer ${apiKey}`, Accept: 'application/json' }

  try {
    await fetchJson(`${base}/api/projects/${pid}/`, { headers })

    const [pv24, pv7, pv30, dauRes, hourlyRes, dailyRes, pagesRes] = await Promise.all([
      hogqlQuery(
        base,
        pid,
        apiKey,
        "SELECT count() AS total FROM events WHERE event = '$pageview' AND timestamp > now() - interval 1 day",
      ),
      hogqlQuery(
        base,
        pid,
        apiKey,
        "SELECT count() AS total FROM events WHERE event = '$pageview' AND timestamp > now() - interval 7 day",
      ).catch(() => null),
      hogqlQuery(
        base,
        pid,
        apiKey,
        "SELECT count() AS total FROM events WHERE event = '$pageview' AND timestamp > now() - interval 30 day",
      ).catch(() => null),
      hogqlQuery(
        base,
        pid,
        apiKey,
        "SELECT uniq(distinct_id) AS dau FROM events WHERE event = '$pageview' AND timestamp > now() - interval 1 day",
      ).catch((e) => ({ __error: e.message })),
      hogqlQuery(
        base,
        pid,
        apiKey,
        "SELECT toStartOfHour(timestamp) AS hour, count() AS c FROM events WHERE event = '$pageview' AND timestamp > now() - interval 1 day GROUP BY hour ORDER BY hour",
      ).catch((e) => ({ __error: e.message })),
      hogqlQuery(
        base,
        pid,
        apiKey,
        "SELECT toStartOfDay(timestamp) AS day, count() AS c FROM events WHERE event = '$pageview' AND timestamp > now() - interval 14 day GROUP BY day ORDER BY day",
      ).catch(() => null),
      hogqlQuery(
        base,
        pid,
        apiKey,
        "SELECT properties.$pathname AS path, count() AS c FROM events WHERE event = '$pageview' AND timestamp > now() - interval 7 day GROUP BY path ORDER BY c DESC LIMIT 8",
      ).catch(() => null),
    ])

    const pageviews24h = hogqlNumber(pv24)
    const pageviews7d = pv7 ? hogqlNumber(pv7) : null
    const pageviews30d = pv30 ? hogqlNumber(pv30) : null

    let dau = null
    let dauError = null
    if (dauRes?.__error) dauError = dauRes.__error
    else if (dauRes) dau = hogqlNumber(dauRes)

    let hourly = []
    let hourlyError = null
    if (hourlyRes?.__error) {
      hourlyError = hourlyRes.__error
    } else if (hourlyRes) {
      const raw = (hourlyRes.results || []).map((row) => ({
        hour: Array.isArray(row) ? row[0] : row.hour,
        count: Number(Array.isArray(row) ? row[1] : row.c) || 0,
      }))
      hourly = fillHourlyBuckets(raw)
    } else {
      hourly = fillHourlyBuckets([])
    }

    const topPages = pagesRes
      ? (pagesRes.results || []).map((row) => ({
          path: Array.isArray(row) ? row[0] || '/' : row.path || '/',
          views: Number(Array.isArray(row) ? row[1] : row.c) || 0,
        }))
      : []

    const daily = dailyRes
      ? (dailyRes.results || []).map((row) => ({
          day: Array.isArray(row) ? row[0] : row.day,
          count: Number(Array.isArray(row) ? row[1] : row.c) || 0,
        }))
      : []

    // Funil aproximado por pathname
    const funnel = {
      home: topPages.filter((p) => p.path === '/' || p.path === '').reduce((a, p) => a + p.views, 0) || null,
      listing: topPages
        .filter((p) => /categoria|produto|catalog/i.test(String(p.path)))
        .reduce((a, p) => a + p.views, 0),
      contact: topPages
        .filter((p) => /contacto|contact|carrinho|orcamento|orçamento/i.test(String(p.path)))
        .reduce((a, p) => a + p.views, 0),
    }

    return {
      configured: true,
      pageviews24h,
      pageviews7d,
      pageviews30d,
      dau,
      dauError,
      hourly,
      hourlyError,
      daily,
      topPages,
      funnel,
      projectId: pid,
    }
  } catch (e) {
    const hint = String(e.message).includes('403')
      ? ' — activa Query: Read + Project: Read na chave phx_ (PostHog EU)'
      : ''
    return {
      configured: true,
      error: `${e.message}${hint}`,
      dau: null,
      pageviews24h: null,
      pageviews7d: null,
      pageviews30d: null,
      hourly: [],
      daily: [],
      topPages: [],
      funnel: null,
    }
  }
}

module.exports = { fetchPosthog }
