#!/usr/bin/env node
/** Gera monitor-hub/config.local.json a partir do .env do repo (sem imprimir secrets). */
const fs = require('fs')
const path = require('path')

const ROOT = path.join(__dirname, '..', '..')
const HUB = path.join(__dirname, '..')
const ENV_PATH = path.join(ROOT, '.env')
const OUT = path.join(HUB, 'config.local.json')
const EXAMPLE = path.join(HUB, 'config.local.example.json')

function parseEnv(content) {
  const out = {}
  for (const line of content.split('\n')) {
    const t = line.trim()
    if (!t || t.startsWith('#')) continue
    const i = t.indexOf('=')
    if (i < 1) continue
    let v = t.slice(i + 1).trim()
    if ((v.startsWith('"') && v.endsWith('"')) || (v.startsWith("'") && v.endsWith("'"))) {
      v = v.slice(1, -1)
    }
    out[t.slice(0, i).trim()] = v
  }
  return out
}

function ntfyJsonUrl(webhook) {
  const m = String(webhook || '').match(/ntfy\.sh\/([^/?#]+)/i)
  return m ? `https://ntfy.sh/${m[1]}/json?poll=1` : ''
}

function main() {
  const base = JSON.parse(fs.readFileSync(EXAMPLE, 'utf8'))
  if (!fs.existsSync(ENV_PATH)) {
    console.error('X .env não encontrado em', ENV_PATH)
    process.exit(1)
  }
  const env = parseEnv(fs.readFileSync(ENV_PATH, 'utf8'))
  const cfg = {
    ...base,
    apiUrl: env.PROD_API_URL || env.API_BASE_URL || base.apiUrl,
    siteUrl: env.PROD_PAGES_URL || base.siteUrl,
    ntfyTopicJsonUrl: ntfyJsonUrl(env.ALERT_WEBHOOK_URL) || base.ntfyTopicJsonUrl,
    alertsLogPath: path.join(ROOT, 'deploy', 'alerts.log'),
    axiom: {
      ...base.axiom,
      token: env.AXIOM_TOKEN || '',
      dataset: env.AXIOM_DATASET || base.axiom.dataset,
    },
    cloudflare: {
      ...base.cloudflare,
      apiToken: env.CLOUDFLARE_API_TOKEN || '',
      accountId: env.CLOUDFLARE_ACCOUNT_ID || '',
      zoneName: env.DIOMIKA_DOMAIN || 'diomika.com',
    },
    posthog: {
      ...base.posthog,
      apiKey: env.POSTHOG_PERSONAL_API_KEY || env.VITE_POSTHOG_KEY || '',
      host: env.VITE_POSTHOG_HOST || base.posthog.host,
      projectId: env.POSTHOG_PROJECT_ID || base.posthog.projectId,
    },
    sentry: {
      ...base.sentry,
      token: env.SENTRY_AUTH_TOKEN || '',
      apiHost: 'https://de.sentry.io',
    },
    uptimerobot: {
      ...base.uptimerobot,
      apiKey: env.UPTIMEROBOT_API_KEY || '',
    },
    ops: {
      apiKey: env.API_OPS_KEY || '',
    },
    supabase: {
      url: env.SUPABASE_URL || env.VITE_SUPABASE_URL || '',
      key: env.SUPABASE_KEY || '',
    },
    github: {
      ...base.github,
      token: env.GITHUB_TOKEN || env.GH_TOKEN || '',
      clientId: env.GITHUB_OAUTH_CLIENT_ID || '',
    },
  }
  fs.writeFileSync(OUT, `${JSON.stringify(cfg, null, 2)}\n`, 'utf8')
  const ok = [
    cfg.ntfyTopicJsonUrl && !cfg.ntfyTopicJsonUrl.includes('SEU_TOPICO'),
    cfg.axiom.token,
    cfg.cloudflare.apiToken,
    cfg.sentry.token,
    cfg.uptimerobot.apiKey,
    cfg.github.token,
  ].filter(Boolean).length
  console.log(`OK config.local.json (${ok}/6 integrações com credencial)`)
}

main()
