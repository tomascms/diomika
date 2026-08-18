const { fetchJson } = require('./http.cjs')

function sinceIso(days) {
  return new Date(Date.now() - days * 86400000).toISOString()
}

function enc(value) {
  return encodeURIComponent(String(value))
}

async function supabaseCount(supabase, table, filters = {}) {
  const base = supabase.url.replace(/\/$/, '')
  const params = new URLSearchParams({ select: 'id' })
  for (const [key, val] of Object.entries(filters)) {
    if (val === null || val === undefined) continue
    params.set(key, `eq.${val}`)
  }
  const url = `${base}/rest/v1/${table}?${params.toString()}`
  const controller = new AbortController()
  const timer = setTimeout(() => controller.abort(), 12000)
  try {
    const res = await fetch(url, {
      method: 'GET',
      signal: controller.signal,
      headers: {
        apikey: supabase.key,
        Authorization: `Bearer ${supabase.key}`,
        Prefer: 'count=exact',
        Range: '0-0',
      },
    })
    if (!res.ok) {
      const text = await res.text().catch(() => '')
      throw new Error(`${res.status}: ${text.slice(0, 120)}`)
    }
    const range = res.headers.get('content-range') || ''
    const total = range.split('/').pop()
    return Number(total) || 0
  } finally {
    clearTimeout(timer)
  }
}

async function supabaseCountSince(supabase, table, sinceIsoStr, extra = {}) {
  const base = supabase.url.replace(/\/$/, '')
  const parts = [`select=id`, `created_at=gte.${enc(sinceIsoStr)}`]
  for (const [key, val] of Object.entries(extra)) {
    parts.push(`${key}=eq.${enc(val)}`)
  }
  const url = `${base}/rest/v1/${table}?${parts.join('&')}`
  const controller = new AbortController()
  const timer = setTimeout(() => controller.abort(), 12000)
  try {
    const res = await fetch(url, {
      method: 'GET',
      signal: controller.signal,
      headers: {
        apikey: supabase.key,
        Authorization: `Bearer ${supabase.key}`,
        Prefer: 'count=exact',
        Range: '0-0',
      },
    })
    if (!res.ok) {
      const text = await res.text().catch(() => '')
      throw new Error(`${res.status}: ${text.slice(0, 120)}`)
    }
    const range = res.headers.get('content-range') || ''
    return Number(range.split('/').pop()) || 0
  } finally {
    clearTimeout(timer)
  }
}

async function fetchBusinessSupabase(supabase) {
  const since1 = sinceIso(1)
  const since7 = sinceIso(7)
  const vis = { visibilidade: true }

  const quotes = {
    total: await supabaseCount(supabase, 'pedidos_orcamento', vis),
    unread: await supabaseCount(supabase, 'pedidos_orcamento', { ...vis, lida: false }),
    today: await supabaseCountSince(supabase, 'pedidos_orcamento', since1, vis),
    last7d: await supabaseCountSince(supabase, 'pedidos_orcamento', since7, vis),
  }
  const contacts = {
    total: await supabaseCount(supabase, 'contact_messages', vis),
    unread: await supabaseCount(supabase, 'contact_messages', { ...vis, lida: false }),
    today: await supabaseCountSince(supabase, 'contact_messages', since1, vis),
    last7d: await supabaseCountSince(supabase, 'contact_messages', since7, vis),
  }
  const orders = {
    total: await supabaseCount(supabase, 'encomendas_internas', vis),
    today: await supabaseCountSince(supabase, 'encomendas_internas', since1, vis),
    last7d: await supabaseCountSince(supabase, 'encomendas_internas', since7, vis),
  }

  return {
    configured: true,
    source: 'supabase',
    quotes,
    contacts,
    orders,
    pipeline: {
      leads_7d: quotes.last7d + contacts.last7d,
      unread_total: quotes.unread + contacts.unread,
    },
    generatedAt: new Date().toISOString(),
  }
}

async function fetchBusinessApi(cfg) {
  const base = (cfg.apiUrl || 'https://api.diomika.com').replace(/\/$/, '')
  const data = await fetchJson(`${base}/ops/analytics/summary`, {
    headers: { 'X-API-Key': cfg.ops.apiKey },
  })
  return {
    configured: true,
    source: 'api',
    quotes: data.quotes,
    contacts: data.contacts,
    orders: data.orders,
    pipeline: data.pipeline,
    generatedAt: data.generated_at,
  }
}

async function fetchBusiness(cfg) {
  const supabase = cfg.supabase?.url && cfg.supabase?.key ? cfg.supabase : null

  if (supabase) {
    try {
      return await fetchBusinessSupabase(supabase)
    } catch (e) {
      if (cfg.ops?.apiKey) {
        try {
          return await fetchBusinessApi(cfg)
        } catch {
          /* fall through */
        }
      }
      return { configured: true, error: e.message, quotes: null, contacts: null, orders: null, pipeline: null }
    }
  }

  if (cfg.ops?.apiKey) {
    try {
      return await fetchBusinessApi(cfg)
    } catch (e) {
      const msg = String(e.message)
      return {
        configured: false,
        error: msg.includes('404')
          ? 'Configuração → Importar do .env (precisa SUPABASE_URL + SUPABASE_KEY)'
          : msg,
        quotes: null,
        contacts: null,
        orders: null,
        pipeline: null,
      }
    }
  }

  return {
    configured: false,
    error: 'Importar do .env na Configuração (Supabase)',
    quotes: null,
    contacts: null,
    orders: null,
    pipeline: null,
  }
}

module.exports = { fetchBusiness }
