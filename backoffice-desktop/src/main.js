import { createApp } from 'vue'
import App from './App.vue'
import router from './router'
import { bootstrapSettings } from './lib/settings'
import './assets/theme.css'
import './assets/premium.css'

bootstrapSettings()

createApp(App).use(router).mount('#app')