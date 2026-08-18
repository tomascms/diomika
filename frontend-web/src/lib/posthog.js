/** PostHog — só após consentimento (CookieBanner). SPA pageviews via router. */
let client = null
let initPromise = null

export function isPosthogReady() {
  return Boolean(client)
}

export async function initPosthog() {
  if (client) return client
  if (initPromise) return initPromise

  const key = import.meta.env.VITE_POSTHOG_KEY || ''
  const host = import.meta.env.VITE_POSTHOG_HOST || 'https://eu.i.posthog.com'
  if (!key) return null

  initPromise = (async () => {
    const { default: posthog } = await import('posthog-js')
    posthog.init(key, {
      api_host: host,
      persistence: 'localStorage',
      autocapture: true,
      capture_pageview: false,
      capture_pageleave: true,
    })
    client = posthog
    window.__diomikaPosthog = posthog
    capturePageview()
    return posthog
  })()

  return initPromise
}

export function capturePageview() {
  if (!client) return
  client.capture('$pageview', {
    $current_url: window.location.href,
    $pathname: window.location.pathname,
  })
}
