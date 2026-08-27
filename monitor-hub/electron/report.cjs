function buildMonthlyReport(snapshot) {
  const d = new Date()
  const month = d.toLocaleString('pt-PT', { month: 'long', year: 'numeric' })
  const posture = snapshot.posture || {}
  const slo = snapshot.slo || {}
  const story = snapshot.story || {}
  const lines = [
    `# Relatório Diomika — ${month}`,
    '',
    `Gerado: ${d.toLocaleString('pt-PT')}`,
    `Projecto: **${snapshot.projectName || 'Diomika'}**`,
    '',
    `Estado operacional: **${(snapshot.score || '—').toUpperCase()}**`,
    `Resumo: ${story.headline || '—'}`,
    `Postura de segurança: **${posture.score ?? '—'} / 100**`,
    '',
    '## Disponibilidade',
    '',
    `- Uptime (monitores): ${slo.uptime30d != null ? slo.uptime30d + '%' : '—'} (alvo ${slo.target ?? 99.5}%)`,
    `- Error budget restante: ${slo.errorBudgetRemaining != null ? slo.errorBudgetRemaining + '%' : '—'}`,
    `- API: ${snapshot.health?.api?.ok ? 'OK' : 'FALHA'} (${snapshot.health?.api?.ms ?? '—'} ms)`,
    `- Loja: ${snapshot.health?.site?.ok ? 'OK' : 'FALHA'}`,
    `- BD: ${snapshot.health?.db?.ok ? 'OK' : 'FALHA'}`,
    '',
    '## Segurança',
    '',
    `- Ameaças / bloqueios 24h: ${snapshot.cloudflare?.threats24h ?? '—'}`,
    `- Pedidos edge 24h: ${snapshot.cloudflare?.requests24h ?? '—'}`,
    `- Admin exposto: ${snapshot.synthetics?.adminExposed ? 'SIM (crítico)' : 'Não'}`,
    `- Checks postura:`,
    ...(posture.checks || []).map((c) => `  - [${c.ok ? 'x' : ' '}] ${c.label}`),
    '',
    '## Erros e qualidade',
    '',
    `- Sentry unresolved: ${snapshot.sentry?.unresolved ?? '—'}`,
    `- Incidentes abertos: ${snapshot.incidents?.openCount ?? 0}`,
    `- MTTR médio: ${snapshot.incidents?.mttrAvgMs != null ? Math.round(snapshot.incidents.mttrAvgMs / 60000) + ' min' : '—'}`,
    '',
    '## Analytics e negócio',
    '',
    `- Pedidos edge 24h: ${snapshot.cloudflare?.requests24h ?? '—'}`,
    `- Pageviews 24h (consentidas): ${snapshot.posthog?.pageviews24h ?? '—'}`,
    `- Pageviews 7d: ${snapshot.posthog?.pageviews7d ?? '—'}`,
    `- Pageviews 30d: ${snapshot.posthog?.pageviews30d ?? '—'}`,
    `- DAU: ${snapshot.posthog?.dau ?? '—'}`,
    `- Orçamentos: hoje ${snapshot.business?.quotes?.today ?? '—'} · 7d ${snapshot.business?.quotes?.last7d ?? '—'} · total ${snapshot.business?.quotes?.total ?? '—'}`,
    `- Contactos 7d: ${snapshot.business?.contacts?.last7d ?? '—'}`,
    `- Encomendas 7d: ${snapshot.business?.orders?.last7d ?? '—'}`,
    `- Por ler: ${snapshot.business?.pipeline?.unread_total ?? '—'}`,
    `- Conversão aprox. visitas→orçamentos (7d): ${snapshot.conversion?.visitsToQuotes7d != null ? snapshot.conversion.visitsToQuotes7d + '%' : '—'}`,
    '',
    '## Jornadas sintéticas',
    '',
    ...(snapshot.synthetics?.steps || []).map(
      (s) => `- ${s.ok ? 'OK' : 'FAIL'} ${s.label} (${s.ms} ms) — ${s.detail || ''}`,
    ),
    '',
    '---',
    '_Sem dados pessoais. Gerado pelo Diomika Command Center._',
    '',
  ]
  return lines.join('\n')
}

function buildMonthlyReportHtml(snapshot) {
  const md = buildMonthlyReport(snapshot)
  const d = new Date()
  const esc = (s) =>
    String(s ?? '')
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
  const score = (snapshot.score || '—').toUpperCase()
  const scoreColor = score === 'OK' ? '#3dd68c' : score === 'WARN' ? '#f59e0b' : '#f87171'
  return `<!DOCTYPE html>
<html lang="pt"><head><meta charset="utf-8"/>
<title>Relatório Diomika — ${esc(d.toLocaleString('pt-PT', { month: 'long', year: 'numeric' }))}</title>
<style>
  body{font-family:Segoe UI,system-ui,sans-serif;max-width:820px;margin:40px auto;padding:0 20px;color:#1a1a1a;line-height:1.5}
  h1{font-size:1.6rem;margin-bottom:4px}
  .meta{color:#666;margin-bottom:24px}
  .score{display:inline-block;padding:6px 14px;border-radius:8px;background:${scoreColor};color:#111;font-weight:700}
  .grid{display:grid;grid-template-columns:1fr 1fr;gap:12px;margin:20px 0}
  .card{border:1px solid #e5e7eb;border-radius:10px;padding:14px}
  .card b{display:block;font-size:1.4rem;margin-top:4px}
  pre{white-space:pre-wrap;background:#f8fafc;padding:16px;border-radius:8px;font-size:13px}
  footer{margin-top:32px;color:#888;font-size:12px}
</style></head><body>
<h1>Relatório Diomika</h1>
<p class="meta">${esc(d.toLocaleString('pt-PT'))} · ${esc(snapshot.projectName || 'Diomika')}</p>
<p><span class="score">${esc(score)}</span> · Postura ${esc(snapshot.posture?.score ?? '—')}/100</p>
<p>${esc(snapshot.story?.headline || '')}</p>
<div class="grid">
  <div class="card">Uptime<div><b>${esc(snapshot.slo?.uptime30d != null ? snapshot.slo.uptime30d + '%' : '—')}</b></div></div>
  <div class="card">Pedidos edge 24h<div><b>${esc(snapshot.cloudflare?.requests24h ?? '—')}</b></div></div>
  <div class="card">Visitas 24h<div><b>${esc(snapshot.posthog?.pageviews24h ?? '—')}</b></div></div>
  <div class="card">Por ler<div><b>${esc(snapshot.business?.pipeline?.unread_total ?? '—')}</b></div></div>
</div>
<pre>${esc(md)}</pre>
<footer>Sem dados pessoais. Diomika Command Center.</footer>
</body></html>`
}

module.exports = { buildMonthlyReport, buildMonthlyReportHtml }
