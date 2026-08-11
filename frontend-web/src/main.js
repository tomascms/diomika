import '@fontsource/arimo/400.css'
import '@fontsource/arimo/500.css'
import '@fontsource/arimo/600.css'
import '@fontsource/arimo/700.css'
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
app.mount('#app')
