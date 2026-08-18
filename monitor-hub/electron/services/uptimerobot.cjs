const { fetchJson } = require('./http.cjs')

async function fetchUptimeRobot(cfg) {
  const apiKey = cfg.uptimerobot?.apiKey
  if (!apiKey) return { configured: false, monitors: [], uptimeRatio: null }
  try {
    const data = await fetchJson('https://api.uptimerobot.com/v2/getMonitors', {
      method: 'POST',
      headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
      body: new URLSearchParams({
        api_key: apiKey,
        format: 'json',
        response_times: '1',
        custom_uptime_ratios: '7',
      }).toString(),
    })
    const monitors = (data.monitors || []).map((m) => ({
      id: m.id,
      name: m.friendly_name,
      url: m.url,
      status: m.status,
      statusLabel: statusLabel(m.status),
      uptime7d: m.custom_uptime_ratio ? `${m.custom_uptime_ratio}%` : '—',
      avgResponse: m.average_response_time,
    }))
    const up = monitors.filter((m) => m.status === 2).length
    const ratio = monitors.length ? Math.round((up / monitors.length) * 100) : null
    return { configured: true, monitors, uptimeRatio: ratio }
  } catch (e) {
    return { configured: true, error: e.message, monitors: [], uptimeRatio: null }
  }
}

function statusLabel(code) {
  const map = { 0: 'Pausado', 1: 'Não verificado', 2: 'Up', 8: 'Parece down', 9: 'Down' }
  return map[code] || `Estado ${code}`
}

module.exports = { fetchUptimeRobot }
