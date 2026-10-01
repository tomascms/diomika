/* Latin 400+600+700 — cobre PT (Latin-1); evita latin-ext (~100KB) no critical path.
   600 é pedido ~15x no CSS (labels, nav, badges) — sem o carregar, o browser
   fazia "font matching" para o peso mais próximo carregado (normalmente 700),
   e todo o texto "semibold" saía involuntariamente a negrito. */
import '@fontsource/arimo/latin-400.css'
import '@fontsource/arimo/latin-600.css'
import '@fontsource/arimo/latin-700.css'
import '@/assets/main.css'

import { createApp } from 'vue'
import App from './App.vue'
import router from './router'
import { useRouteMeta } from '@/composables/usePageMeta'
import { injectOrganizationJsonLd } from '@/composables/useStructuredData'

const app = createApp(App)
app.use(router)
useRouteMeta(router)
injectOrganizationJsonLd()
app.config.errorHandler = (err) => {
  console.error('[Diomika]', err)
}
// Bust stale module graph on custom domain after partial deploys.
if (typeof window !== 'undefined') window.__DIOMIKA_BUILD__ = '2026-08-27f'
app.mount('#app')
