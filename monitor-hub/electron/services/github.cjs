const { execFile } = require('child_process')
const { promisify } = require('util')
const { fetchJson } = require('./http.cjs')

const execFileAsync = promisify(execFile)

async function tryGhCliToken() {
  if (process.platform === 'win32') {
    try {
      const { stdout } = await execFileAsync('gh', ['auth', 'token'], { timeout: 5000 })
      const token = stdout.trim()
      return token.length > 10 ? token : ''
    } catch {
      return ''
    }
  }
  try {
    const { stdout } = await execFileAsync('gh', ['auth', 'token'], { timeout: 5000 })
    return stdout.trim()
  } catch {
    return ''
  }
}

async function startDeviceFlow(clientId) {
  if (!clientId) throw new Error('clientId em falta — cria OAuth App em github.com/settings/developers')
  return fetchJson('https://github.com/login/device/code', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      client_id: clientId,
      scope: 'read:org repo workflow',
    }),
  })
}

async function pollDeviceToken(clientId, deviceCode) {
  return fetchJson('https://github.com/login/oauth/access_token', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      client_id: clientId,
      device_code: deviceCode,
      grant_type: 'urn:ietf:params:oauth:grant-type:device_code',
    }),
  })
}

async function fetchWorkflowRuns(token, repo, limit = 8) {
  if (!token) return { configured: false, runs: [] }
  const data = await fetchJson(
    `https://api.github.com/repos/${repo}/actions/workflows/ci.yml/runs?per_page=${limit}`,
    { headers: { Authorization: `Bearer ${token}`, 'X-GitHub-Api-Version': '2022-11-28' } },
  )
  const runs = (data.workflow_runs || []).map((r) => ({
    id: r.id,
    name: r.name || 'CI',
    status: r.status,
    conclusion: r.conclusion,
    branch: r.head_branch,
    event: r.event,
    url: r.html_url,
    createdAt: r.created_at,
    updatedAt: r.updated_at,
  }))
  return { configured: true, runs }
}

async function fetchUptimeRuns(token, repo, limit = 5) {
  if (!token) return { configured: false, runs: [] }
  try {
    const data = await fetchJson(
      `https://api.github.com/repos/${repo}/actions/workflows/uptime.yml/runs?per_page=${limit}`,
      { headers: { Authorization: `Bearer ${token}`, 'X-GitHub-Api-Version': '2022-11-28' } },
    )
    const runs = (data.workflow_runs || []).map((r) => ({
      id: r.id,
      name: r.name || 'Uptime',
      conclusion: r.conclusion,
      status: r.status,
      createdAt: r.created_at,
      url: r.html_url,
    }))
    return { configured: true, runs }
  } catch {
    return { configured: false, runs: [] }
  }
}

async function fetchLatestRelease(token, repo) {
  if (!token) return null
  try {
    const data = await fetchJson(
      `https://api.github.com/repos/${repo}/releases/latest`,
      { headers: { Authorization: `Bearer ${token}`, 'X-GitHub-Api-Version': '2022-11-28' } },
    )
    return { tag: data.tag_name, name: data.name, publishedAt: data.published_at, url: data.html_url }
  } catch {
    return null
  }
}

module.exports = {
  tryGhCliToken,
  startDeviceFlow,
  pollDeviceToken,
  fetchWorkflowRuns,
  fetchUptimeRuns,
  fetchLatestRelease,
}
