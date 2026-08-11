import { getImageUrl, getSignedImageUrl } from '@/lib/supabase'

export const PLACEHOLDER = '/placeholder.svg'

function storagePrivateEnabled() {
  return /^(1|true|yes)$/i.test(String(import.meta.env.VITE_STORAGE_PRIVATE || '').trim())
}

/** URL segura para CSS background-image — bloqueia javascript: e quotes. */
export function safeCssUrl(url) {
  if (!url || typeof url !== 'string') return ''
  const trimmed = url.trim()
  if (!/^https?:\/\//i.test(trimmed) && !trimmed.startsWith('/')) return ''
  if (/["'()\\]/.test(trimmed)) return ''
  return trimmed
}

/**
 * Resolve path de storage → URL utilizável.
 * Com VITE_STORAGE_PRIVATE=1 usa URL assinada (async).
 */
export async function resolveImageUrl(path, placeholder = PLACEHOLDER) {
  if (!path) return placeholder
  if (typeof path === 'string' && path.trim().startsWith('data:')) {
    return path.trim()
  }
  if (storagePrivateEnabled()) {
    const signed = await getSignedImageUrl(path)
    return signed || placeholder
  }
  return getImageUrl(path) || placeholder
}

/** Sync — só para paths já resolvidos (https) ou modo público. */
export function formatImageUrl(path, placeholder = PLACEHOLDER) {
  if (!path) return placeholder
  if (storagePrivateEnabled()) {
    const value = typeof path === 'string' ? path.trim() : ''
    if (/^https?:\/\//i.test(value) || value.startsWith('data:') || value.startsWith('/')) {
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
