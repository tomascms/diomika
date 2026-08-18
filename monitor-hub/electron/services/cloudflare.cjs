const { fetchJson } = require('./http.cjs')

async function fetchCloudflare(cfg) {
  const { apiToken, zoneName } = cfg.cloudflare || {}
  if (!apiToken) return { configured: false, threats24h: null, requests24h: null, zoneStatus: null }
  try {
    const zones = await fetchJson(
      `https://api.cloudflare.com/client/v4/zones?name=${encodeURIComponent(zoneName || 'diomika.com')}`,
      { headers: { Authorization: `Bearer ${apiToken}` } },
    )
    const zone = zones.result?.[0]
    if (!zone) return { configured: true, error: 'Zona não encontrada', threats24h: null, requests24h: null }

    let threats24h = null
    let requests24h = null
    try {
      const since = new Date(Date.now() - 24 * 3600 * 1000).toISOString()
      const until = new Date().toISOString()
      const analytics = await fetchJson(
        `https://api.cloudflare.com/client/v4/zones/${zone.id}/analytics/dashboard?since=${since}&until=${until}`,
        { headers: { Authorization: `Bearer ${apiToken}` } },
      )
      const totals = analytics.result?.totals || {}
      threats24h = totals.threats?.all ?? totals.threats ?? null
      requests24h = totals.requests?.all ?? totals.requests ?? null
    } catch {
      /* analytics may need higher plan */
    }

    return {
      configured: true,
      zoneStatus: zone.status,
      zoneName: zone.name,
      threats24h,
      requests24h,
    }
  } catch (e) {
    return { configured: true, error: e.message, threats24h: null, requests24h: null }
  }
}

module.exports = { fetchCloudflare }
