const { fetchJson } = require('./http.cjs')

async function fetchAxiom(cfg) {
  const { token, dataset } = cfg.axiom || {}
  if (!token || !dataset) return { configured: false, errorRate: [], latencyP95: null, recentErrors: [] }
  const start = new Date(Date.now() - 24 * 3600 * 1000).toISOString()
  const end = new Date().toISOString()
  const headers = { Authorization: `Bearer ${token}`, 'Content-Type': 'application/json' }
  try {
    const errorQuery = await fetchJson(`https://api.axiom.co/v1/datasets/${dataset}/query`, {
      method: 'POST',
      headers,
      body: JSON.stringify({
        apl: "['diomika'] | where ['level'] == 'error' or ['severity'] == 'error' | summarize count() by bin(_time, 1h) | sort by _time asc | limit 24",
        startTime: start,
        endTime: end,
      }),
    })
    const errorRate = (errorQuery.tables?.[0]?.rows || []).map((row) => ({
      hour: row[0],
      count: Number(row[1] || 0),
    }))

    let latencyP95 = null
    let recentErrors = []
    try {
      const latQuery = await fetchJson(`https://api.axiom.co/v1/datasets/${dataset}/query`, {
        method: 'POST',
        headers,
        body: JSON.stringify({
          apl: "['diomika'] | where isnotnull(['duration_ms']) | summarize p95=take_percentile(['duration_ms'], 95)",
          startTime: new Date(Date.now() - 3600 * 1000).toISOString(),
          endTime: end,
        }),
      })
      latencyP95 = latQuery.tables?.[0]?.rows?.[0]?.[0] ?? null
    } catch {
      /* optional */
    }

    try {
      const recent = await fetchJson(`https://api.axiom.co/v1/datasets/${dataset}/query`, {
        method: 'POST',
        headers,
        body: JSON.stringify({
          apl: "['diomika'] | where ['level'] == 'error' or ['severity'] == 'error' | project _time, message, path, status | sort by _time desc | limit 15",
          startTime: start,
          endTime: end,
        }),
      })
      recentErrors = (recent.tables?.[0]?.rows || []).map((row) => ({
        ts: row[0],
        title: row[1] || 'Erro API',
        message: [row[2], row[3]].filter(Boolean).join(' · '),
        source: 'axiom',
      }))
    } catch {
      /* optional */
    }

    return { configured: true, errorRate, latencyP95, recentErrors }
  } catch (e) {
    return { configured: true, error: e.message, errorRate: [], latencyP95: null, recentErrors: [] }
  }
}

module.exports = { fetchAxiom }
