/**
 * Cache do catálogo público na Cloudflare (perto do visitante).
 *
 * A API está numa VM nos EUA: cada pedido directo custava ~200–300 ms só de
 * ida e volta. Aqui as leituras públicas do catálogo ficam em cache no PoP da
 * Cloudflare (Lisboa/Madrid para clientes portugueses) e saem do mesmo domínio
 * da loja — sem CORS nem pedidos OPTIONS.
 *
 * Frescura: a chave da cache inclui a versão do catálogo (GET /catalogo/version,
 * que muda a cada escrita no backoffice). A versão é consultada no máximo de 5
 * em 5 s por PoP, por isso o que se publica aparece na loja em segundos.
 *
 * Só GET de rotas públicas de catálogo. Formulários (POST) continuam a ir
 * directamente a api.diomika.com.
 */
const API_ORIGIN = 'https://api.diomika.com'
const VERSION_TTL_SECONDS = 5
const ENTRY_TTL_SECONDS = 3600

const CACHEABLE = [
  /^\/categorias$/,
  /^\/categorias\/slug\/[^/]+$/,
  /^\/catalogo\/meta$/,
  /^\/catalogo\/search$/,
  /^\/catalogo\/modelo-detalhe\/[^/]+$/,
  /^\/catalogo\/[a-z_]+\/modelos-catalogo\/[^/]+$/,
  /^\/catalogo\/[a-z_]+\/modelo-detalhe\/slug\/[^/]+\/[^/]+$/,
  /^\/catalogo\/[a-z_]+\/modelo-detalhe\/[^/]+$/,
]

function json(status, body, extraHeaders = {}) {
  return new Response(JSON.stringify(body), {
    status,
    headers: { 'Content-Type': 'application/json; charset=utf-8', 'Cache-Control': 'no-store', ...extraHeaders },
  })
}

function upstreamHeaders(request) {
  const h = new Headers({ Accept: 'application/json', 'User-Agent': 'DiomikaEdge/1.0' })
  const ip = request.headers.get('CF-Connecting-IP')
  if (ip) h.set('X-Forwarded-For', ip)
  return h
}

async function catalogVersion(context, origin) {
  const cache = caches.default
  const key = new Request(`${origin}/__edge/catalog-version`)
  const hit = await cache.match(key)
  if (hit) return hit.text()
  try {
    const resp = await fetch(`${API_ORIGIN}/catalogo/version`, { headers: upstreamHeaders(context.request) })
    if (!resp.ok) return null
    const { v } = await resp.json()
    const value = String(v || '')
    if (!value) return null
    context.waitUntil(
      cache.put(key, new Response(value, { headers: { 'Cache-Control': `public, max-age=${VERSION_TTL_SECONDS}` } })),
    )
    return value
  } catch {
    return null
  }
}

function forBrowser(body, status, contentType, cacheState) {
  return new Response(body, {
    status,
    headers: {
      'Content-Type': contentType || 'application/json; charset=utf-8',
      // O browser revalida sempre — a cache rápida é esta, no PoP.
      'Cache-Control': 'no-cache',
      'X-Edge-Cache': cacheState,
    },
  })
}

export async function onRequest(context) {
  const { request } = context
  if (request.method !== 'GET' && request.method !== 'HEAD') {
    return json(405, { detail: 'Método não suportado.' }, { Allow: 'GET, HEAD' })
  }

  const url = new URL(request.url)
  const path = url.pathname.replace(/^\/api/, '') || '/'
  if (!CACHEABLE.some((re) => re.test(path))) {
    return json(404, { detail: 'Não encontrado.' })
  }

  const upstreamUrl = `${API_ORIGIN}${path}${url.search}`
  const version = await catalogVersion(context, url.origin)
  const cache = caches.default
  const cacheKey = version ? new Request(`${url.origin}/__edge/v/${version}${path}${url.search}`) : null

  if (cacheKey) {
    const hit = await cache.match(cacheKey)
    if (hit) {
      return forBrowser(hit.body, hit.status, hit.headers.get('Content-Type'), 'HIT')
    }
  }

  let upstream
  try {
    upstream = await fetch(upstreamUrl, { headers: upstreamHeaders(request) })
  } catch {
    return json(502, { detail: 'Sem ligação ao servidor. Tente de novo dentro de instantes.' })
  }

  const contentType = upstream.headers.get('Content-Type')
  const body = await upstream.arrayBuffer()
  if (cacheKey && upstream.status === 200) {
    context.waitUntil(
      cache.put(
        cacheKey,
        new Response(body, {
          status: 200,
          headers: { 'Content-Type': contentType || 'application/json', 'Cache-Control': `public, max-age=${ENTRY_TTL_SECONDS}` },
        }),
      ),
    )
  }
  return forBrowser(body, upstream.status, contentType, version ? 'MISS' : 'BYPASS')
}
