import { watch } from 'vue'

const DEFAULT_TITLE = 'Diomika'
const DEFAULT_DESC = 'Catálogo Diomika — explore categorias, modelos e peça orçamento online.'
const SITE_ORIGIN = typeof window !== 'undefined' ? window.location.origin : ''

const ROUTE_META = {
  home: {
    title: 'Diomika — Catálogo',
    description: 'Explore o catálogo por categoria e peça orçamento.',
  },
  products: {
    title: 'Catálogo',
    description: 'Modelos e variantes disponíveis.',
  },
  'product-detail': {
    title: 'Detalhe do produto',
    description: 'Especificações, cores e pedido de orçamento.',
  },
  cart: {
    title: 'Pedido de orçamento',
    description: 'Revise o seu pedido e envie o orçamento.',
  },
  contact: {
    title: 'Contacto',
    description: 'Entre em contacto connosco.',
  },
  privacy: {
    title: 'Política de privacidade',
    description: 'Como tratamos os seus dados pessoais.',
  },
  'not-found': {
    title: 'Página não encontrada',
    description: DEFAULT_DESC,
  },
}

function setMeta(name, content) {
  if (!content) return
  let el = document.querySelector(`meta[name="${name}"]`)
  if (!el) {
    el = document.createElement('meta')
    el.setAttribute('name', name)
    document.head.appendChild(el)
  }
  el.setAttribute('content', content)
}

function setOg(property, content) {
  if (!content) return
  let el = document.querySelector(`meta[property="${property}"]`)
  if (!el) {
    el = document.createElement('meta')
    el.setAttribute('property', property)
    document.head.appendChild(el)
  }
  el.setAttribute('content', content)
}

function setCanonical(href) {
  if (!href) return
  let el = document.querySelector('link[rel="canonical"]')
  if (!el) {
    el = document.createElement('link')
    el.setAttribute('rel', 'canonical')
    document.head.appendChild(el)
  }
  el.setAttribute('href', href)
}

export function applyPageMeta({ title, description, image, path } = {}) {
  const fullTitle = title ? `${title} | Diomika` : DEFAULT_TITLE
  const desc = description || DEFAULT_DESC
  document.title = fullTitle
  setMeta('description', desc)
  setOg('og:title', fullTitle)
  setOg('og:description', desc)
  setOg('og:type', 'website')
  setOg('og:locale', 'pt_PT')
  setMeta('twitter:card', 'summary_large_image')
  setMeta('twitter:title', fullTitle)
  setMeta('twitter:description', desc)
  if (image) {
    const img = image.startsWith('http') ? image : `${SITE_ORIGIN}${image.startsWith('/') ? '' : '/'}${image}`
    setOg('og:image', img)
  }
  if (path && SITE_ORIGIN) {
    setCanonical(`${SITE_ORIGIN}${path.startsWith('/') ? path : `/${path}`}`)
  }
}

export function useRouteMeta(router) {
  router.afterEach((to) => {
    const base = ROUTE_META[to.name] || {}
    applyPageMeta({
      title: to.meta?.title || base.title,
      description: to.meta?.description || base.description,
      path: to.fullPath,
    })
  })
}

export function watchDynamicTitle(source, getMeta) {
  watch(
    source,
    () => {
      const meta = getMeta()
      if (meta?.title) applyPageMeta(meta)
    },
    { immediate: true, deep: true },
  )
}
