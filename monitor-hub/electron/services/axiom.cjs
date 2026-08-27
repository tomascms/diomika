const { fetchJson } = require('./http.cjs')

function queryRoot(cfg) {
  const base = (cfg.axiom?.apiUrl || 'https://api.axiom.co').replace(/\/$/, '')
  if (/edge\.axiom\.co|ingest/i.test(base)) return 'https://api.axiom.co'
  return base
}

/** Normalize Axiom tabular / legacy table shapes into { hour, count }[]. */
function parseSeries(payload) {
  const table = payload?.tables?.[0]
  if (!table) return []

  if (Array.isArray(table.rows) && table.rows.length) {
    return table.rows.map((row) => ({
      hour: row[0],
      count: Number(row[1] || 0),
    }))
  }

  // tabular: columns[] parallel arrays + fields[]
  const fields = (table.fields || []).map((f) => (typeof f === 'string' ? f : f?.name || ''))
  const cols = table.columns || []
  if (!cols.length) return []

  const timeIdx = Math.max(
    0,
    fields.findIndex((n) => /time|_time|bin/i.test(n)),
  )
  let countIdx = fields.findIndex((n) => /count|c$/i.test(n))
  if (countIdx < 0) countIdx = cols.length > 1 ? 1 : 0

  const times = cols[timeIdx] || []
  const counts = cols[countIdx] || []
  const n = Math.max(times.length, counts.length)
  const out = []
  for (let i = 0; i < n; i++) {
    out.push({ hour: times[i], count: Number(counts[i] || 0) })
  }
  return out
}

function parseRows(payload, mapFn) {
  const table = payload?.tables?.[0]
  if (!table) return []
  if (Array.isArray(table.rows)) return table.rows.map(mapFn)

  const fields = (table.fields || []).map((f) => (typeof f === 'string' ? f : f?.name || ''))
  const cols = table.columns || []
  if (!cols.length) return []
  const n = Math.max(...cols.map((c) => c.length))
  const rows = []
  for (let i = 0; i < n; i++) {
    rows.push(cols.map((c) => c[i]))
  }
  // Prefer named field order for mapFn expecting positional rows
  if (fields.length) {
    /* rows already column-aligned */
  }
  return rows.map(mapFn)
}

async function aplQuery(root, headers, dataset, apl, startTime, endTime) {
  const body = JSON.stringify({ apl, startTime, endTime })
  try {
    return await fetchJson(`${root}/v1/datasets/_apl?format=tabular`, {
      method: 'POST',
      headers,
      body,
    })
  } catch {
    return fetchJson(`${root}/v1/datasets/${encodeURIComponent(dataset)}/query`, {
      method: 'POST',
      headers,
      body,
    })
  }
}

async function fetchAxiom(cfg) {
  const { token, dataset } = cfg.axiom || {}
  if (!token || !dataset) {
    return { configured: false, errorRate: [], latencyP95: null, recentErrors: [], privilegedHits: [] }
  }

  const start = new Date(Date.now() - 24 * 3600 * 1000).toISOString()
  const end = new Date().toISOString()
  const headers = { Authorization: `Bearer ${token}`, 'Content-Type': 'application/json' }
  const root = queryRoot(cfg)
  const ds = dataset.replace(/'/g, '')

  try {
    const errorQuery = await aplQuery(
      root,
      headers,
      ds,
      `['${ds}'] | where tostring(['level']) =~ '(?i)error' or tostring(['severity']) =~ '(?i)error' or ['status'] >= 500 | summarize count() by bin(_time, 1h) | sort by _time asc`,
      start,
      end,
    )
    let errorRate = parseSeries(errorQuery)

    // Fallback: any events volume if no error field
    if (!errorRate.length) {
      try {
        const vol = await aplQuery(
          root,
          headers,
          ds,
          `['${ds}'] | summarize count() by bin(_time, 1h) | sort by _time asc`,
          start,
          end,
        )
        errorRate = parseSeries(vol).map((r) => ({ ...r, volume: true }))
      } catch {
        /* optional */
      }
    }

    let latencyP95 = null
    let recentErrors = []
    let privilegedHits = []
    let eventCount24h = null

    try {
      const latQuery = await aplQuery(
        root,
        headers,
        ds,
        `['${ds}'] | where isnotnull(['duration_ms']) or isnotnull(['duration']) | summarize p95=percentile(coalesce(['duration_ms'], ['duration']), 95)`,
        new Date(Date.now() - 3600 * 1000).toISOString(),
        end,
      )
      const table = latQuery.tables?.[0]
      if (table?.rows?.[0]?.[0] != null) latencyP95 = table.rows[0][0]
      else if (table?.columns?.[0]?.[0] != null) latencyP95 = table.columns[0][0]
    } catch {
      /* optional */
    }

    try {
      const countQ = await aplQuery(
        root,
        headers,
        ds,
        `['${ds}'] | summarize count()`,
        start,
        end,
      )
      const t = countQ.tables?.[0]
      eventCount24h = t?.rows?.[0]?.[0] ?? t?.columns?.[0]?.[0] ?? null
    } catch {
      /* optional */
    }

    try {
      const recent = await aplQuery(
        root,
        headers,
        ds,
        `['${ds}'] | where tostring(['level']) =~ '(?i)error' or tostring(['severity']) =~ '(?i)error' or ['status'] >= 500 | project _time, ['msg'], ['message'], ['logger'], ['path'], ['status'] | sort by _time desc | limit 15`,
        start,
        end,
      )
      recentErrors = parseRows(recent, (row) => ({
        ts: row[0],
        title: row[1] || row[2] || `HTTP ${row[5] || 'erro'}`,
        message: [row[3], row[4], row[5]].filter(Boolean).join(' · '),
        source: 'axiom',
      }))
    } catch {
      /* optional */
    }

    try {
      const priv = await aplQuery(
        root,
        headers,
        ds,
        `['${ds}'] | where tostring(['path']) contains '/admin' or tostring(['path']) contains '/system' or tostring(['msg']) contains '/admin' | summarize count() by bin(_time, 1h) | sort by _time desc | limit 12`,
        start,
        end,
      )
      privilegedHits = parseSeries(priv)
    } catch {
      /* optional */
    }

    return {
      configured: true,
      errorRate: errorRate.filter((r) => !r.volume),
      volumeRate: errorRate.filter((r) => r.volume),
      latencyP95,
      recentErrors,
      privilegedHits,
      eventCount24h: eventCount24h != null ? Number(eventCount24h) : null,
    }
  } catch (e) {
    const msg = String(e.message || e)
    const friendly = /403|401|query|read|permission/i.test(msg)
      ? 'Token Axiom sem permissão de leitura no dataset'
      : /fetch failed|ENOTFOUND|certificate/i.test(msg)
        ? 'Sem ligação ao Axiom (rede/TLS)'
        : msg
    return {
      configured: true,
      error: friendly,
      errorRate: [],
      latencyP95: null,
      recentErrors: [],
      privilegedHits: [],
    }
  }
}

module.exports = { fetchAxiom }
