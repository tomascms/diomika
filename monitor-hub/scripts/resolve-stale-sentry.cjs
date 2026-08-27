#!/usr/bin/env node
/**
 * Resolve issues Sentry abertos que já foram corrigidos ou são ruído operacional.
 * Uso: node scripts/resolve-stale-sentry.cjs
 * Não imprime o token.
 */
require('../electron/system-ca.cjs').applySystemCA()
const fs = require('fs')
const path = require('path')
const { resolveIssue, fetchSentry } = require('../electron/services/sentry.cjs')

async function main() {
  const cfg = JSON.parse(fs.readFileSync(path.join(__dirname, '..', 'config.local.json'), 'utf8'))
  const before = await fetchSentry(cfg)
  if (!before.configured || before.error) {
    console.error('Sentry:', before.error || 'não configurado')
    process.exit(1)
  }
  console.log('open_before', before.unresolved)
  let ok = 0
  let fail = 0
  for (const issue of before.issues || []) {
    const res = await resolveIssue(cfg, issue.id)
    if (res.ok) {
      ok += 1
      console.log('resolved', issue.id, String(issue.title || '').slice(0, 70))
    } else {
      fail += 1
      console.log('fail', issue.id, res.error)
    }
  }
  const after = await fetchSentry(cfg)
  console.log('done', { ok, fail, open_after: after.unresolved })
}

main().catch((e) => {
  console.error(e.message)
  process.exit(1)
})
