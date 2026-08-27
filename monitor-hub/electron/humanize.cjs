/** Mensagens humanas — a home nunca mostra códigos crus. */

function humanizeError(source, raw) {
  const msg = String(raw || '')
  if (!msg) return null

  if (/Token Axiom sem permissão|axiom.*leitura/i.test(msg) || (/403/i.test(msg) && /axiom|query/i.test(msg + source))) {
    return {
      short: 'Registo de erros da API sem permissão de leitura',
      detail: 'Cria um token Axiom com permissão de leitura no dataset e importa de novo o .env.',
      code: 'axiom-query',
    }
  }
  if (/Firewall Services|firewallEvents|does not have access to the path/i.test(msg)) {
    return {
      short: 'Feed WAF detalhado limitado',
      detail: 'Edge analytics está OK. Para paths/eventos WAF, adiciona Zone → Firewall Services → Read ao token.',
      code: 'cf-waf',
    }
  }
  if (
    /Zone Analytics Read|analytics\.read|zone\.analytics/i.test(msg) ||
    (/cloudflare/i.test(source) && /permission|Analytics/i.test(msg) && !/firewall/i.test(msg))
  ) {
    return {
      short: 'Cloudflare sem permissão de analytics',
      detail: 'No token Cloudflare activa Zone Analytics Read para a zona diomika.com.',
      code: 'cf-analytics',
    }
  }
  if (/403/i.test(msg) && /posthog/i.test(source + msg)) {
    return {
      short: 'PostHog sem permissão de consulta',
      detail: 'Usa uma Personal API Key (phx_) com Query:Read e Project:Read na região EU.',
      code: 'posthog-query',
    }
  }
  if (/401|unauthorized/i.test(msg)) {
    return {
      short: `Credencial inválida (${source})`,
      detail: 'Reimporta o .env ou cola um token novo em Ligações.',
      code: 'auth',
    }
  }
  if (/fetch failed|ENOTFOUND|ECONNREFUSED|timeout|AbortError/i.test(msg)) {
    return {
      short: `Sem ligação a ${source}`,
      detail: 'Rede, firewall ou serviço temporariamente indisponível.',
      code: 'network',
    }
  }
  if (/zona não encontrada/i.test(msg)) {
    return {
      short: 'Zona Cloudflare não encontrada',
      detail: 'Confirma cloudflare.zoneName (ex.: diomika.com).',
      code: 'cf-zone',
    }
  }
  // Strip raw technical noise for display
  const cleaned = msg
    .replace(/\b\d{3}:\s*/g, '')
    .replace(/token does not have access[^.]*/gi, 'sem permissão')
    .slice(0, 160)
  return {
    short: `${labelSource(source)} com problema`,
    detail: cleaned,
    code: 'generic',
  }
}

function labelSource(source) {
  const map = {
    axiom: 'Registo de erros',
    posthog: 'Analytics de visitas',
    cloudflare: 'Cloudflare',
    sentry: 'Sentry',
    business: 'Dados de negócio',
    uptime: 'Uptime',
    github: 'GitHub',
  }
  return map[source] || source
}

function buildStory(snapshot) {
  const items = []
  const push = (severity, title, detail, action = null) => {
    items.push({ severity, title, detail, action })
  }

  for (const r of snapshot.recommendations || []) {
    push(r.severity || 'warning', r.title, r.detail, r.action)
  }

  // Integrações — só frase humana, nunca o erro cru na story
  for (const err of snapshot.integrationErrors || []) {
    // Edge OK = não assustes com WAF ACL residual
    if (err.name === 'cloudflare' && snapshot.cloudflare?.requests24h != null) continue
    const h = humanizeError(err.name, err.error)
    if (h) {
      push('info', h.short, h.detail, 'setup-analytics')
    }
  }

  // Deduplicate by title
  const seen = new Set()
  const unique = []
  for (const it of items) {
    if (seen.has(it.title)) continue
    seen.add(it.title)
    unique.push(it)
  }

  const critical = unique.filter((i) => i.severity === 'critical').length
  const warnings = unique.filter((i) => i.severity === 'warning').length
  let headline = 'Tudo sob controlo'
  let tone = 'ok'
  if (critical > 0) {
    headline =
      critical === 1
        ? '1 problema urgente precisa de ti'
        : `${critical} problemas urgentes precisam de ti`
    tone = 'critical'
  } else if (warnings > 0 || unique.length > 0) {
    const n = warnings || unique.length
    headline = n === 1 ? '1 coisa pede atenção' : `${n} coisas pedem atenção`
    tone = 'warn'
  }

  return {
    tone,
    headline,
    items: unique.slice(0, 8),
    criticalCount: critical,
    warningCount: warnings,
  }
}

module.exports = { humanizeError, buildStory, labelSource }
