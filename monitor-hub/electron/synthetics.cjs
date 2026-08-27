const { timedFetch } = require('./services/http.cjs')

async function runSynthetics(cfg) {
  const api = (cfg.apiUrl || 'https://api.diomika.com').replace(/\/$/, '')
  const site = (cfg.siteUrl || 'https://www.diomika.com').replace(/\/$/, '')
  const steps = []

  async function step(id, label, fn) {
    const started = Date.now()
    try {
      const result = await fn()
      steps.push({ id, label, ok: !!result.ok, ms: result.ms ?? Date.now() - started, detail: result.detail || '' })
    } catch (e) {
      steps.push({ id, label, ok: false, ms: Date.now() - started, detail: e.message })
    }
  }

  await step('site-home', 'Loja homepage', async () => {
    const r = await timedFetch(site)
    return { ok: r.ok, ms: r.ms, detail: `HTTP ${r.status || '?'}` }
  })

  await step('api-health', 'API /health', async () => {
    const r = await timedFetch(`${api}/health`)
    return { ok: r.ok && r.text.includes('online'), ms: r.ms, detail: r.text.slice(0, 80) }
  })

  await step('api-categories', 'API /categorias', async () => {
    const r = await timedFetch(`${api}/categorias`)
    return { ok: r.ok, ms: r.ms, detail: `HTTP ${r.status || '?'}` }
  })

  await step('site-categorias', 'Loja /categorias', async () => {
    const r = await timedFetch(`${site}/categorias`)
    return { ok: r.ok, ms: r.ms, detail: `HTTP ${r.status || '?'}` }
  })

  await step('admin-blocked', 'Admin público bloqueado', async () => {
    const r = await timedFetch(`${api}/admin/crud/categories`)
    // Expect block: 401/403/404/429 or Cloudflare challenge — NOT 200 with data
    const blocked = !r.ok || r.status === 401 || r.status === 403 || r.status === 404 || r.status === 429
    const exposed = r.ok && r.status === 200
    return {
      ok: blocked && !exposed,
      ms: r.ms,
      detail: exposed ? 'CRÍTICO: HTTP 200 sem gate' : `HTTP ${r.status || '?'} (esperado bloqueio)`,
    }
  })

  await step('system-blocked', 'System público bloqueado', async () => {
    const r = await timedFetch(`${api}/system/workspace`)
    const blocked = !r.ok || r.status === 401 || r.status === 403 || r.status === 404 || r.status === 429
    const exposed = r.ok && r.status === 200
    return {
      ok: blocked && !exposed,
      ms: r.ms,
      detail: exposed ? 'CRÍTICO: HTTP 200 sem gate' : `HTTP ${r.status || '?'} (esperado bloqueio)`,
    }
  })

  const failed = steps.filter((s) => !s.ok)
  const adminExposed = steps.some((s) => (s.id === 'admin-blocked' || s.id === 'system-blocked') && !s.ok && /CRÍTICO/.test(s.detail))
  const catalogFail =
    (steps.some((s) => s.id === 'api-categories' && !s.ok) ||
      steps.some((s) => s.id === 'site-categorias' && !s.ok)) &&
    steps.some((s) => s.id === 'site-home' && s.ok)

  return {
    ok: failed.length === 0,
    steps,
    failedCount: failed.length,
    adminExposed,
    catalogFail,
  }
}

module.exports = { runSynthetics }
