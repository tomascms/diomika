async function fetchJson(url, options = {}, timeoutMs = 15000) {
  const controller = new AbortController()
  const timer = setTimeout(() => controller.abort(), timeoutMs)
  try {
    const res = await fetch(url, {
      ...options,
      signal: controller.signal,
      headers: {
        Accept: 'application/json',
        ...(options.headers || {}),
      },
    })
    const text = await res.text()
    let data = null
    try {
      data = text ? JSON.parse(text) : null
    } catch {
      data = { raw: text }
    }
    if (!res.ok) {
      const msg = data?.message || data?.errors?.[0]?.message || res.statusText
      throw new Error(`${res.status}: ${msg}`)
    }
    return data
  } finally {
    clearTimeout(timer)
  }
}

async function timedFetch(url, options = {}, timeoutMs = 12000) {
  const t0 = Date.now()
  const res = await fetch(url, { ...options, signal: AbortSignal.timeout(timeoutMs) })
  const text = await res.text()
  return { ok: res.ok, status: res.status, ms: Date.now() - t0, text }
}

module.exports = { fetchJson, timedFetch }
