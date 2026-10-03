<script setup>
import { ref, onMounted } from 'vue'
import { initPosthog } from '@/lib/posthog'

const CONSENT_KEY = 'diomika_cookie_consent'
const posthogKey = import.meta.env.VITE_POSTHOG_KEY || ''

const visible = ref(false)

const accept = async () => {
  localStorage.setItem(CONSENT_KEY, 'accepted')
  visible.value = false
  await initPosthog()
}

const reject = () => {
  localStorage.setItem(CONSENT_KEY, 'rejected')
  visible.value = false
}

onMounted(async () => {
  const saved = localStorage.getItem(CONSENT_KEY)
  if (saved === 'accepted') {
    await initPosthog()
    return
  }
  if (saved === 'rejected') return
  if (!posthogKey) return
  visible.value = true
})
</script>

<template>
  <Transition name="slide-up">
    <aside v-if="visible" class="cookie-banner" role="dialog" aria-label="Consentimento de cookies">
      <p>
        Utilizamos analytics (PostHog) para melhorar o site — só com o seu consentimento.
        <RouterLink to="/cookies">Cookies</RouterLink> ·
        <RouterLink to="/privacidade">Privacidade</RouterLink>.
      </p>
      <div class="cookie-actions">
        <button type="button" class="btn btn-secondary btn-sm" @click="reject">Recusar</button>
        <button type="button" class="btn btn-primary btn-sm" @click="accept">Aceitar</button>
      </div>
    </aside>
  </Transition>
</template>

<style scoped>
.cookie-banner {
  position: fixed;
  bottom: 1rem;
  left: 50%;
  transform: translateX(-50%);
  z-index: 2000;
  width: min(540px, calc(100% - 2rem));
  background: linear-gradient(135deg, var(--color-surface) 0%, rgba(59, 130, 246, 0.02) 100%);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-md);
  box-shadow: 0 20px 40px rgba(0, 0, 0, 0.15), 0 0 1px rgba(59, 130, 246, 0.5);
  padding: 1.25rem 1.5rem;
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 1rem;
  backdrop-filter: blur(8px);
  animation: slideUpBanner 0.4s cubic-bezier(0.34, 1.56, 0.64, 1);
  position: relative;
  overflow: hidden;
}

.cookie-banner::before {
  content: '';
  position: absolute;
  top: 0;
  left: 0;
  right: 0;
  height: 1px;
  background: linear-gradient(90deg, transparent 0%, rgba(59, 130, 246, 0.3) 50%, transparent 100%);
  pointer-events: none;
}

.cookie-banner p {
  margin: 0;
  flex: 1 1 240px;
  font-size: 0.95rem;
  color: var(--color-ink-soft);
  line-height: 1.5;
  font-weight: 500;
  position: relative;
  z-index: 1;
}

.cookie-banner a {
  color: var(--color-link);
  text-decoration: none;
  font-weight: 600;
  transition: all 0.2s ease;
  position: relative;
}

.cookie-banner a:hover {
  color: var(--color-link-hover);
  text-decoration: underline;
}

.cookie-actions {
  display: flex;
  gap: 0.6rem;
  position: relative;
  z-index: 1;
}

.btn-sm {
  padding: 0.5rem 1rem;
  font-size: 0.85rem;
  font-weight: 600;
  border-radius: 6px;
  transition: all 0.3s cubic-bezier(0.34, 1.56, 0.64, 1);
  cursor: pointer;
  box-shadow: 0 2px 4px rgba(0, 0, 0, 0.08);
}

.btn-sm:hover {
  transform: translateY(-2px);
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.15);
}

.slide-up-enter-active,
.slide-up-leave-active {
  transition: opacity 0.3s cubic-bezier(0.34, 1.56, 0.64, 1),
              transform 0.3s cubic-bezier(0.34, 1.56, 0.64, 1);
}

.slide-up-enter-from,
.slide-up-leave-to {
  opacity: 0;
  transform: translate(-50%, 16px);
}

@keyframes slideUpBanner {
  from {
    opacity: 0;
    transform: translateX(-50%) translateY(16px);
  }
  to {
    opacity: 1;
    transform: translateX(-50%) translateY(0);
  }
}
</style>
