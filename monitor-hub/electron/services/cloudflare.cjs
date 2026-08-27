const { fetchJson } = require('./http.cjs')

async function graphql(apiToken, query, variables = {}) {
  return fetchJson('https://api.cloudflare.com/client/v4/graphql', {
    method: 'POST',
    headers: {
      Authorization: `Bearer ${apiToken}`,
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({ query, variables }),
  })
}

function humanizeCfError(msg) {
  const m = String(msg || '')
  if (/does not have access to the path|firewallEvents/i.test(m)) {
    return 'Token sem Firewall Services Read — edge analytics funciona; feed WAF detalhado indisponível.'
  }
  if (/analytics\.read|zone\.analytics/i.test(m)) {
    return 'Token Cloudflare sem Zone Analytics Read — edita o token na Cloudflare e volta a importar.'
  }
  if (/permission/i.test(m)) {
    return 'Token Cloudflare sem permissões suficientes para analytics.'
  }
  return m.slice(0, 180)
}

function isWafAclError(msg) {
  return /does not have access to the path|firewallEvents|firewall.?services/i.test(String(msg || ''))
}

async function fetchCloudflare(cfg) {
  const { apiToken, zoneName, accountId } = cfg.cloudflare || {}
  if (!apiToken) {
    return { configured: false, threats24h: null, requests24h: null, zoneStatus: null, waf: null }
  }
  try {
    const zones = await fetchJson(
      `https://api.cloudflare.com/client/v4/zones?name=${encodeURIComponent(zoneName || 'diomika.com')}`,
      { headers: { Authorization: `Bearer ${apiToken}` } },
    )
    const zone = zones.result?.[0]
    if (!zone) {
      return { configured: true, error: 'Zona não encontrada', threats24h: null, requests24h: null, waf: null }
    }

    let threats24h = null
    let requests24h = null
    let bytes24h = null
    let cachedRequests24h = null
    let analyticsError = null
    let wafError = null
    let topPaths = []
    let topCountries = []
    let recentEvents = []
    let seriesHourly = []

    const sinceDt = new Date(Date.now() - 24 * 3600 * 1000).toISOString()
    const untilDt = new Date().toISOString()
    const sinceDate = sinceDt.slice(0, 10)
    const untilDate = untilDt.slice(0, 10)

    try {
      const reqQuery = `
        query ($zoneTag: String!, $since: Date!, $until: Date!) {
          viewer {
            zones(filter: { zoneTag: $zoneTag }) {
              httpRequests1dGroups(limit: 5, filter: { date_geq: $since, date_lt: $until }) {
                sum { requests threats bytes cachedRequests }
              }
            }
          }
        }`
      const reqData = await graphql(apiToken, reqQuery, {
        zoneTag: zone.id,
        since: sinceDate,
        until: untilDate,
      })
      if (reqData.errors?.length) {
        analyticsError = humanizeCfError(reqData.errors.map((e) => e.message).join('; '))
      } else {
        const sum = reqData.data?.viewer?.zones?.[0]?.httpRequests1dGroups?.[0]?.sum
        if (sum) {
          requests24h = sum.requests ?? null
          threats24h = sum.threats ?? null
          bytes24h = sum.bytes ?? null
          cachedRequests24h = sum.cachedRequests ?? null
        }
      }
    } catch (e) {
      analyticsError = humanizeCfError(e.message)
    }

    // Country breakdown via analytics (no Firewall permission needed)
    try {
      const countryQuery = `
        query ($zoneTag: String!, $since: Date!, $until: Date!) {
          viewer {
            zones(filter: { zoneTag: $zoneTag }) {
              httpRequests1dGroups(
                limit: 12
                filter: { date_geq: $since, date_lt: $until }
                orderBy: [sum_requests_DESC]
              ) {
                sum { requests threats }
                dimensions { clientCountryName }
              }
            }
          }
        }`
      const cData = await graphql(apiToken, countryQuery, {
        zoneTag: zone.id,
        since: sinceDate,
        until: untilDate,
      })
      if (!cData.errors?.length) {
        const groups = cData.data?.viewer?.zones?.[0]?.httpRequests1dGroups || []
        topCountries = groups
          .filter((g) => g.dimensions?.clientCountryName)
          .map((g) => ({
            country: g.dimensions.clientCountryName,
            count: g.sum?.requests || 0,
            threats: g.sum?.threats || 0,
          }))
          .slice(0, 8)
      }
    } catch {
      /* optional */
    }

    // Hourly series for charts
    try {
      const hourQuery = `
        query ($zoneTag: String!, $since: Time!, $until: Time!) {
          viewer {
            zones(filter: { zoneTag: $zoneTag }) {
              httpRequests1hGroups(
                limit: 24
                filter: { datetime_geq: $since, datetime_lt: $until }
                orderBy: [datetime_ASC]
              ) {
                dimensions { datetime }
                sum { requests threats }
              }
            }
          }
        }`
      const hData = await graphql(apiToken, hourQuery, {
        zoneTag: zone.id,
        since: sinceDt,
        until: untilDt,
      })
      if (!hData.errors?.length) {
        seriesHourly = (hData.data?.viewer?.zones?.[0]?.httpRequests1hGroups || []).map((g) => ({
          t: g.dimensions?.datetime,
          requests: g.sum?.requests || 0,
          threats: g.sum?.threats || 0,
        }))
      }
    } catch {
      /* optional */
    }

    try {
      const fwQuery = `
        query ($zoneTag: String!, $since: Time!, $until: Time!) {
          viewer {
            zones(filter: { zoneTag: $zoneTag }) {
              firewallEventsAdaptiveGroups(
                limit: 20
                filter: { datetime_geq: $since, datetime_leq: $until }
                orderBy: [count_DESC]
              ) {
                count
                dimensions { action clientCountryName clientRequestPath }
              }
              firewallEventsAdaptive(
                limit: 15
                filter: { datetime_geq: $since, datetime_leq: $until }
                orderBy: [datetime_DESC]
              ) {
                action
                clientCountryName
                clientRequestPath
                datetime
                source
              }
            }
          }
        }`
      const fwData = await graphql(apiToken, fwQuery, {
        zoneTag: zone.id,
        since: sinceDt,
        until: untilDt,
      })
      if (fwData.errors?.length) {
        const msg = fwData.errors.map((e) => e.message).join('; ')
        wafError = humanizeCfError(msg)
        // Never poison analyticsError with WAF ACL noise
        if (!isWafAclError(msg) && !analyticsError) {
          analyticsError = humanizeCfError(msg)
        }
      }
      const z = fwData.data?.viewer?.zones?.[0]
      const groups = z?.firewallEventsAdaptiveGroups || []
      topPaths = groups
        .filter((g) => g.dimensions?.clientRequestPath)
        .slice(0, 8)
        .map((g) => ({
          path: g.dimensions.clientRequestPath,
          count: g.count,
          action: g.dimensions.action,
          country: g.dimensions.clientCountryName,
        }))
      if (!topCountries.length) {
        const byCountry = new Map()
        for (const g of groups) {
          const c = g.dimensions?.clientCountryName || '?'
          byCountry.set(c, (byCountry.get(c) || 0) + (g.count || 0))
        }
        topCountries = [...byCountry.entries()]
          .sort((a, b) => b[1] - a[1])
          .slice(0, 6)
          .map(([country, count]) => ({ country, count }))
      }
      recentEvents = (z?.firewallEventsAdaptive || []).map((e) => ({
        action: e.action,
        country: e.clientCountryName,
        path: e.clientRequestPath,
        at: e.datetime,
        source: e.source,
      }))
    } catch (e) {
      wafError = humanizeCfError(e.message)
      if (!isWafAclError(e.message) && !analyticsError) {
        analyticsError = wafError
      }
    }

    const softError = requests24h == null && threats24h == null && analyticsError ? analyticsError : null

    const threatRatio =
      requests24h > 0 && threats24h != null
        ? Math.round((threats24h / requests24h) * 1000) / 10
        : null

    return {
      configured: true,
      zoneStatus: zone.status,
      zoneName: zone.name,
      zoneId: zone.id,
      accountId: accountId || null,
      threats24h,
      requests24h,
      bytes24h,
      cachedRequests24h,
      threatRatio,
      seriesHourly,
      analyticsError,
      wafError,
      error: softError || undefined,
      waf: {
        topPaths,
        topCountries,
        recentEvents,
        blockedApprox: threats24h,
        limited: Boolean(wafError && isWafAclError(wafError)),
      },
    }
  } catch (e) {
    return { configured: true, error: e.message, threats24h: null, requests24h: null, waf: null }
  }
}

module.exports = { fetchCloudflare }
