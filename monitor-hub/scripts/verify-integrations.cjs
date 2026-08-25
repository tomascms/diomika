#!/usr/bin/env node
/** Verifica integrações sem imprimir secrets. */
const cfg = JSON.parse(require('fs').readFileSync(require('path').join(__dirname, '..', 'config.local.json'), 'utf8'))
const { fetchSentry } = require('../electron/services/sentry.cjs')
const { fetchPosthog } = require('../electron/services/posthog.cjs')
const { fetchUptimeRobot } = require('../electron/services/uptimerobot.cjs')

async function main() {
  const [sentry, posthog, uptime] = await Promise.all([
    fetchSentry(cfg),
    fetchPosthog(cfg),
    fetchUptimeRobot(cfg),
  ])
  console.log('Sentry:', sentry.configured ? (sentry.error || `ok (${sentry.unresolved} issues)`) : 'not configured')
  console.log('PostHog:', posthog.configured ? (posthog.error || `ok (pv24h=${posthog.pageviews24h}, dau=${posthog.dau})`) : 'not configured')
  console.log('UptimeRobot:', uptime.configured ? (uptime.error || `ok (${uptime.monitors?.length ?? 0} monitors)`) : 'not configured')
}

main().catch((e) => {
  console.error(e.message)
  process.exit(1)
})
