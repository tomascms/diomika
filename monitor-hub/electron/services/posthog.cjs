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

async function fetchPosthog(cfg) {
  const { apiKey, projectId, host } = cfg.posthog || {}
  if (!apiKey || !projectId) return { configured: false, dau: null, pageviews24h: null }

  const base = apiBase(host)
  const pid = String(projectId)
  const headers = { Authorization: `Bearer ${apiKey}`, Accept: 'application/json' }

  try {
    await fetchJson(`${base}/api/projects/${pid}/`, { headers })

    const total = await hogqlQuery(
      base,
      pid,
      apiKey,
      "SELECT count() AS total FROM events WHERE event = '$pageview' AND timestamp > now() - interval 1 day",
    )
    const pageviews24h = hogqlNumber(total)

    let dau = null
    try {
      const dauRes = await hogqlQuery(
        base,
        pid,
        apiKey,
        "SELECT count(DISTINCT person_id) AS dau FROM events WHERE event = '$pageview' AND timestamp > now() - interval 1 day",
      )
      dau = hogqlNumber(dauRes) || null
    } catch {
      /* optional */
    }

    let hourly = []
    try {
      const hourlyRes = await hogqlQuery(
        base,
        pid,
        apiKey,
        "SELECT toStartOfHour(timestamp) AS hour, count() AS c FROM events WHERE event = '$pageview' AND timestamp > now() - interval 1 day GROUP BY hour ORDER BY hour",
      )
      hourly = (hourlyRes.results || []).map((row) => Number(Array.isArray(row) ? row[1] : Object.values(row)[1]) || 0)
    } catch {
      /* optional */
    }

    return { configured: true, pageviews24h, dau, hourly, projectId: pid }
  } catch (e) {
    const hint = String(e.message).includes('403')
      ? ' — activa Query: Read + Project: Read na chave phx_ (PostHog EU)'
      : ''
    return { configured: true, error: `${e.message}${hint}`, dau: null, pageviews24h: null }
  }
}

module.exports = { fetchPosthog }
