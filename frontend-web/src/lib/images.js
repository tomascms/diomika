import { getImageUrl, storageObjectPath } from '@/lib/supabaseConfig'

export const PLACEHOLDER = '/placeholder.svg'

/** Presets para Image Transformation (fallback automático se o plano não tiver). */
export const IMG_THUMB = { width: 640, quality: 70, resize: 'contain' }
export const IMG_CARD = { width: 720, quality: 75, resize: 'contain' }
export const IMG_HERO = { width: 1200, quality: 78, resize: 'contain' }
export const IMG_DETAIL = { width: 1400, quality: 80, resize: 'contain' }

const signedMemo = new Map()
const PERSIST_KEY = 'diomika_signed_v2'
const PERSIST_TTL_MS = 50 * 60 * 1000

function storagePrivateEnabled() {
  return /^(1|true|yes)$/i.test(String(import.meta.env.VITE_STORAGE_PRIVATE || '').trim())
}

function transformEnabled() {
  // default on — se o projecto não tiver Image Transformation, cai para full-size
  const raw = String(import.meta.env.VITE_IMAGE_TRANSFORM ?? '1').trim()
  return /^(1|true|yes)$/i.test(raw)
}

function cacheKey(path, transform) {
  const base = storageObjectPath(path) || String(path || '').trim()
  if (!base) return ''
  if (!transform) return base
  return `${base}::w${transform.width || ''}q${transform.quality || ''}`
}

function readPersist(key) {
  if (!key || typeof sessionStorage === 'undefined') return null
  try {
    const raw = sessionStorage.getItem(PERSIST_KEY)
    if (!raw) return null
    const bag = JSON.parse(raw)
    const row = bag?.[key]
    if (!row?.url || !row?.exp || Date.now() > row.exp) return null
    return row.url
  } catch {
    return null
  }
}

function writePersist(key, url) {
  if (!key || !url || typeof sessionStorage === 'undefined') return
  try {
    const raw = sessionStorage.getItem(PERSIST_KEY)
    const bag = raw ? JSON.parse(raw) : {}
    bag[key] = { url, exp: Date.now() + PERSIST_TTL_MS }
    // Evita crescer sem limite
    const keys = Object.keys(bag)
    if (keys.length > 400) {
      keys
        .sort((a, b) => (bag[a].exp || 0) - (bag[b].exp || 0))
        .slice(0, keys.length - 300)
        .forEach((k) => delete bag[k])
    }
    sessionStorage.setItem(PERSIST_KEY, JSON.stringify(bag))
  } catch {
    /* quota / private mode */
  }
}

/** URL segura para CSS background-image — bloqueia javascript: e quotes. */
export function safeCssUrl(url) {
  if (!url || typeof url !== 'string') return ''
  const trimmed = url.trim()
  if (!/^https?:\/\//i.test(trimmed) && !trimmed.startsWith('/')) return ''
  if (/["'()\\]/.test(trimmed)) return ''
  return trimmed
}

function isReadyUrl(value) {
  return (
    /^https?:\/\//i.test(value) ||
    value.startsWith('data:') ||
    value.startsWith('/')
  )
}

/**
 * Resolve vários paths em lote (1 request createSignedUrls quando privado).
 * options.transform — thumbnail Supabase (opcional).
 */
export async function resolveImageUrls(paths, placeholder = PLACEHOLDER, options = {}) {
  const input = Array.isArray(paths) ? paths : []
  if (!input.length) return []

  const transform =
    options.transform && transformEnabled() ? options.transform : null

  if (!storagePrivateEnabled()) {
    return input.map((path) => {
      if (!path) return placeholder
      if (typeof path === 'string' && path.trim().startsWith('data:')) return path.trim()
      return getImageUrl(path) || placeholder
    })
  }

  const out = new Array(input.length).fill(placeholder)
  const needIdx = []
  const needPaths = []

  for (let i = 0; i < input.length; i++) {
    const path = input[i]
    if (!path) continue
    if (typeof path === 'string' && path.trim().startsWith('data:')) {
      out[i] = path.trim()
      continue
    }
    const key = cacheKey(path, transform)
    if (!key) continue
    if (isReadyUrl(key.split('::')[0]) && /^https?:\/\//i.test(String(path).trim())) {
      out[i] = String(path).trim()
      continue
    }
    const mem = signedMemo.get(key)
    if (mem) {
      out[i] = mem
      continue
    }
    const persisted = readPersist(key)
    if (persisted) {
      signedMemo.set(key, persisted)
      out[i] = persisted
      continue
    }
    needIdx.push(i)
    needPaths.push(path)
  }

  if (needPaths.length) {
    const { getSignedImageUrls } = await import('@/lib/supabase')
    const signed = await getSignedImageUrls(needPaths, 3600, transform)
    for (let j = 0; j < needPaths.length; j++) {
      const url = signed[j] || placeholder
      const key = cacheKey(needPaths[j], transform)
      if (key && url && url !== placeholder) {
        signedMemo.set(key, url)
        writePersist(key, url)
      }
      out[needIdx[j]] = url
    }
  }

  return out
}

/**
 * Resolve path de storage → URL utilizável.
 * Com VITE_STORAGE_PRIVATE=1 usa URL assinada (async).
 */
export async function resolveImageUrl(path, placeholder = PLACEHOLDER, options = {}) {
  const [url] = await resolveImageUrls([path], placeholder, options)
  return url
}

/** Sync — só para paths já resolvidos (https) ou modo público. */
export function formatImageUrl(path, placeholder = PLACEHOLDER) {
  if (!path) return placeholder
  if (storagePrivateEnabled()) {
    const value = typeof path === 'string' ? path.trim() : ''
    if (isReadyUrl(value)) {
      return value || placeholder
    }
    return placeholder
  }
  const url = getImageUrl(path)
  return url || placeholder
}

export function parseDimensions(dim) {
  const match = String(dim).match(/^(\d+)x(\d+)$/)
  if (!match) return 0
  return parseInt(match[1], 10) * parseInt(match[2], 10)
}
