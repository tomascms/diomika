/* Latin 400+700 — cobre PT (Latin-1); evita latin-ext (~100KB) no critical path */
import '@fontsource/arimo/latin-400.css'
import '@fontsource/arimo/latin-700.css'
import '@/assets/main.css'

import { createApp } from 'vue'
import App from './App.vue'
import router from './router'
import { useRouteMeta } from '@/composables/usePageMeta'

const app = createApp(App)
app.use(router)
useRouteMeta(router)
app.config.errorHandler = (err) => {
  console.error('[Diomika]', err)
}
// Bust stale module graph on custom domain after partial deploys.
if (typeof window !== 'undefined') window.__DIOMIKA_BUILD__ = '2026-08-27c'
app.mount('#app')
