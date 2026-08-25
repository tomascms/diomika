import { createClient } from '@supabase/supabase-js'

const supabaseUrl = import.meta.env.VITE_SUPABASE_URL || ''
const supabaseAnonKey = import.meta.env.VITE_SUPABASE_ANON_KEY || ''
const storageBucket = import.meta.env.VITE_SUPABASE_STORAGE_BUCKET || 'product-images'

export const supabaseConfigured = Boolean(supabaseUrl && supabaseAnonKey)

export const supabase = supabaseConfigured
  ? createClient(supabaseUrl, supabaseAnonKey)
  : null

/** Subscreve Realtime sem derrubar a UI se WebSocket falhar. */
export function subscribeRealtime(channel) {
  if (!channel) return null
  if (typeof WebSocket === 'undefined') {
    console.warn('[Diomika] Realtime indisponível: WebSocket não suportado')
    return null
  }
  try {
    channel.subscribe((status, err) => {
      if (status === 'SUBSCRIBED') {
        console.debug('[Diomika] Realtime ligado:', channel.topic)
      } else if (status === 'CHANNEL_ERROR' || status === 'TIMED_OUT') {
        console.warn('[Diomika] Realtime indisponível:', err?.message || status, err?.cause || '')
      }
    })
    return channel
  } catch (err) {
    console.warn('[Diomika] Realtime indisponível:', err?.message || err)
    return null
  }
}

function normalizeStorageUrl(url) {
  if (!url || !/^https?:\/\//i.test(url)) return url

  let cleaned = url.replace('/object/public/public/', '/object/public/')
  const marker = '/storage/v1/object/public/'
  const idx = cleaned.indexOf(marker)
  if (idx === -1) return cleaned

  const prefix = cleaned.slice(0, idx + marker.length)
  let path = cleaned.slice(idx + marker.length).replace(/^\/+/, '')
  if (!path || path.startsWith(`${storageBucket}/`)) return cleaned

  return `${prefix}${storageBucket}/${path}`
}

/** Extrai path interno a partir de URL pública/assinada do Storage. */
export function storageObjectPath(path) {
  if (!path) return ''
  if (Array.isArray(path)) return storageObjectPath(path[0])
  if (typeof path === 'object') {
    if (path?.url) return storageObjectPath(path.url)
    return ''
  }
  let value = String(path).trim()
  if (!value) return ''
  if (/^data:/i.test(value)) return ''

  const markers = [
    `/storage/v1/object/public/${storageBucket}/`,
    `/storage/v1/object/sign/${storageBucket}/`,
    `/storage/v1/object/authenticated/${storageBucket}/`,
  ]
  for (const marker of markers) {
    const idx = value.indexOf(marker)
    if (idx !== -1) {
      let rest = value.slice(idx + marker.length)
      rest = rest.split('?')[0]
      return decodeURIComponent(rest.replace(/^\/+/, ''))
    }
  }

  if (/^https?:\/\//i.test(value)) return ''

  if (/^[\[{]/.test(value)) {
    try {
      const parsed = JSON.parse(value)
      if (Array.isArray(parsed)) return storageObjectPath(parsed[0])
      if (typeof parsed === 'string') return storageObjectPath(parsed)
    } catch {
      // continua
    }
  }

  let storagePath = value.replace(/\\/g, '/').replace(/^\/+/, '')
  if (storagePath.startsWith(`${storageBucket}/`)) {
    storagePath = storagePath.slice(storageBucket.length + 1)
  }
  return storagePath
}

export function getImageUrl(path) {
  if (!path) return ''

  if (Array.isArray(path)) {
    return getImageUrl(path[0])
  }

  if (typeof path === 'object') {
    if (path?.url) return getImageUrl(path.url)
    return ''
  }

  let value = String(path).trim()
  if (!value) return ''

  if (/^https?:\/\//i.test(value) || /^data:/i.test(value)) {
    return normalizeStorageUrl(value)
  }

  if (!supabaseConfigured) return ''

  const storagePath = storageObjectPath(value)
  if (!storagePath) return ''

  const { data } = supabase.storage.from(storageBucket).getPublicUrl(storagePath)
  return data?.publicUrl || ''
}

/** URL assinada para bucket privado (cutover: ver deploy/storage_private_cutover.py). */
export async function getSignedImageUrl(path, expiresIn = 3600) {
  if (!path || !supabaseConfigured) return ''
  if (typeof path === 'string' && /^data:/i.test(path.trim())) return path.trim()

  const storagePath = storageObjectPath(path)
  if (!storagePath) {
    // URL externa (não Storage) — devolver como está
    const raw = String(Array.isArray(path) ? path[0] : path).trim()
    return /^https?:\/\//i.test(raw) ? normalizeStorageUrl(raw) : ''
  }
  const { data, error } = await supabase.storage
    .from(storageBucket)
    .createSignedUrl(storagePath, expiresIn)
  if (error || !data?.signedUrl) return ''
  return data.signedUrl
}
