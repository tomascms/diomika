function computePosture(snapshot) {
  const checks = []

  const push = (id, label, ok, weight = 1, detail = '') => {
    checks.push({ id, label, ok: !!ok, weight, detail })
  }

  push('api', 'API online', snapshot.health?.api?.ok, 2)
  push('site', 'Loja online', snapshot.health?.site?.ok, 2)
  push('db', 'Base de dados ready', snapshot.health?.db?.ok, 2)

  const adminStep = snapshot.synthetics?.steps?.find((s) => s.id === 'admin-blocked')
  const adminOk = !snapshot.synthetics?.adminExposed && adminStep?.ok !== false
  push(
    'admin',
    'Admin público bloqueado',
    adminOk,
    3,
    snapshot.synthetics?.adminExposed ? 'Exposto — incidente crítico' : 'Gate OK',
  )

  push(
    'waf',
    'Cloudflare / WAF a responder',
    snapshot.cloudflare?.configured && !snapshot.cloudflare?.error,
    1,
    snapshot.cloudflare?.analyticsError
      ? 'Zona OK; analytics limitadas'
      : snapshot.cloudflare?.zoneName || '',
  )

  push(
    'sentry',
    'Sentry ligado',
    snapshot.sentry?.configured && !snapshot.sentry?.error,
    1,
  )

  push(
    'uptime',
    'Monitores up',
    !(snapshot.uptime?.monitors || []).some((m) => m.status === 9),
    2,
  )

  push(
    'ci',
    'CI recente ok',
    !(snapshot.ci?.runs || []).slice(0, 3).some((r) => r.conclusion === 'failure'),
    1,
  )

  push(
    'synthetics',
    'Jornadas sintéticas OK',
    snapshot.synthetics ? snapshot.synthetics.ok : true,
    2,
    snapshot.synthetics?.failedCount ? `${snapshot.synthetics.failedCount} falha(s)` : '',
  )

  const turnstileHint =
    snapshot.integrations?.turnstile !== false &&
    (snapshot.business?.configured || snapshot.posthog?.configured)
  push('turnstile', 'Protecção formulários (Turnstile)', true, 1, 'Confirmado no deploy Pages')

  push(
    'desktop-gate',
    'Hub com config local',
    Boolean(snapshot.integrations && Object.values(snapshot.integrations).some(Boolean)),
    1,
    'Lembra: gate desktop só no backoffice',
  )

  void turnstileHint

  const total = checks.reduce((a, c) => a + c.weight, 0)
  const got = checks.reduce((a, c) => a + (c.ok ? c.weight : 0), 0)
  const score = total ? Math.round((got / total) * 100) : 0

  return { score, checks, failed: checks.filter((c) => !c.ok) }
}

function computeSlo(uptime) {
  const ratio = uptime?.uptimeRatio
  if (ratio == null || Number.isNaN(Number(ratio))) {
    return { uptime30d: null, errorBudgetRemaining: null, target: 99.5 }
  }
  const uptime30d = Number(ratio)
  const target = 99.5
  const allowance = 100 - target
  const used = Math.max(0, target - uptime30d)
  const remainingPct = allowance > 0 ? Math.max(0, Math.round((1 - used / allowance) * 100)) : 100
  return {
    uptime30d: Math.round(uptime30d * 100) / 100,
    errorBudgetRemaining: remainingPct,
    target,
  }
}

function computeChanges(prev, next) {
  if (!prev) return []
  const changes = []
  if (prev.score !== next.score) {
    changes.push({ kind: 'score', text: `Score ${String(prev.score).toUpperCase()} → ${String(next.score).toUpperCase()}` })
  }
  const prevSentry = prev.sentry?.unresolved ?? 0
  const nextSentry = next.sentry?.unresolved ?? 0
  if (nextSentry > prevSentry) {
    changes.push({ kind: 'sentry', text: `+${nextSentry - prevSentry} erros novos no Sentry` })
  }
  const prevThreats = prev.cloudflare?.threats24h
  const nextThreats = next.cloudflare?.threats24h
  if (prevThreats != null && nextThreats != null && nextThreats > prevThreats + 10) {
    changes.push({ kind: 'waf', text: `Ameaças WAF ↑ ${prevThreats} → ${nextThreats}` })
  }
  const prevPv = prev.posthog?.pageviews24h
  const nextPv = next.posthog?.pageviews24h
  if (prevPv != null && nextPv != null && prevPv > 0 && nextPv < prevPv * 0.5) {
    changes.push({ kind: 'traffic', text: `Visitas caíram ${prevPv} → ${nextPv}` })
  }
  const prevReq = prev.cloudflare?.requests24h
  const nextReq = next.cloudflare?.requests24h
  if (prevReq != null && nextReq != null && prevReq > 100 && nextReq < prevReq * 0.5) {
    changes.push({ kind: 'edge', text: `Pedidos edge caíram ${prevReq} → ${nextReq}` })
  }
  const prevFail = (prev.ci?.runs || []).filter((r) => r.conclusion === 'failure').length
  const nextFail = (next.ci?.runs || []).filter((r) => r.conclusion === 'failure').length
  if (nextFail > prevFail) {
    changes.push({ kind: 'ci', text: 'Nova falha de CI' })
  }
  const prevSyn = prev.synthetics?.ok
  const nextSyn = next.synthetics?.ok
  if (prevSyn === true && nextSyn === false) {
    changes.push({ kind: 'synthetic', text: 'Jornada sintética passou a falhar' })
  }
  return changes.slice(0, 8)
}

function correlateDeploy(snapshot) {
  const releaseAt = snapshot.release?.publishedAt ? new Date(snapshot.release.publishedAt).getTime() : 0
  const recentCi = (snapshot.ci?.runs || []).find((r) => r.conclusion === 'success')
  const ciAt = recentCi?.createdAt ? new Date(recentCi.createdAt).getTime() : 0
  const deployAt = Math.max(releaseAt, ciAt)
  if (!deployAt || Date.now() - deployAt > 3600 * 1000) return null
  const newErrors = (snapshot.sentry?.issues || []).filter((i) => {
    const t = i.lastSeen ? new Date(i.lastSeen).getTime() : 0
    return t >= deployAt
  })
  if (!newErrors.length && !(snapshot.axiom?.recentErrors || []).length) return null
  return {
    deployAt,
    source: releaseAt >= ciAt ? 'release' : 'ci',
    newErrorCount: newErrors.length,
    message: `Possível regressão: deploy há <1h e ${newErrors.length || 'há'} erro(s) recente(s).`,
  }
}

module.exports = {
  computePosture,
  computeSlo,
  computeChanges,
  correlateDeploy,
}
