const { fetchJson } = require('./http.cjs')

const SENTRY_HOSTS = ['https://de.sentry.io', 'https://sentry.io']

async function listProjects(token, org, preferredHost) {
  const hosts = preferredHost
    ? [preferredHost.replace(/\/$/, ''), ...SENTRY_HOSTS.filter((h) => h !== preferredHost.replace(/\/$/, ''))]
    : SENTRY_HOSTS
  let lastError = null
  for (const base of hosts) {
    try {
      const data = await fetchJson(`${base}/api/0/organizations/${org}/projects/`, {
        headers: { Authorization: `Bearer ${token}` },
      })
      return { base, projects: Array.isArray(data) ? data : [] }
    } catch (e) {
      lastError = e
    }
  }
  throw lastError || new Error('Sentry indisponível')
}

function pickProject(projects, { project, projectId }) {
  if (projectId) {
    const byId = projects.find((p) => String(p.id) === String(projectId))
    if (byId) return byId
  }
  if (project) {
    const bySlug = projects.find((p) => p.slug === project)
    if (bySlug) return bySlug
  }
  return projects[0] || null
}

async function fetchSentry(cfg) {
  const { token, org, project, projectId, apiHost } = cfg.sentry || {}
  if (!token) return { configured: false, unresolved: 0, issues: [] }
  try {
    const { base, projects } = await listProjects(token, org, apiHost)
    const match = pickProject(projects, { project, projectId })
    if (!match) {
      return { configured: true, error: 'Nenhum projecto Sentry encontrado', unresolved: 0, issues: [] }
    }
    const data = await fetchJson(
      `${base}/api/0/projects/${org}/${match.slug}/issues/?query=is:unresolved&limit=12`,
      { headers: { Authorization: `Bearer ${token}` } },
    )
    const issues = (Array.isArray(data) ? data : []).map((i) => ({
      id: i.id,
      title: i.title,
      level: i.level,
      count: i.count,
      lastSeen: i.lastSeen,
      permalink: i.permalink,
      culprit: i.culprit,
    }))
    return {
      configured: true,
      unresolved: issues.length,
      issues,
      projectSlug: match.slug,
      projectName: match.name,
    }
  } catch (e) {
    return { configured: true, error: e.message, unresolved: 0, issues: [] }
  }
}

module.exports = { fetchSentry }
