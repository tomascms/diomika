<script setup>
import { computed, onMounted, ref } from 'vue'
import { useRoute, useRouter, RouterView } from 'vue-router'
import { useWorkspace } from '@/composables/useWorkspace'
import { mapApiError, clearSession, readSessionUser } from '@/lib/settings'
import { api } from '@/lib/api'
import Sidebar from '@/components/Sidebar.vue'

const route = useRoute()
const router = useRouter()
const { sidebarItems, loadWorkspace, workspace, error, loading } = useWorkspace()
const currentTable = computed(() => route.params.table || '')
const sidebarOpen = ref(false)
const sessionUser = ref(readSessionUser())

const pageTitle = computed(() => {
  if (route.name === 'schema') return 'Schema & Sync'
  return workspace.value?.sidebar?.[currentTable.value]?.label
    || workspace.value?.tables?.[currentTable.value]?.label
    || 'Painel'
})

const apiOnline = ref(null)

const checkHealth = async () => {
  try {
    await api.health()
    apiOnline.value = true
  } catch {
    apiOnline.value = false
  }
}

const retryAll = async () => {
  await checkHealth()
  await loadWorkspace(true).catch(() => {})
}

const closeSidebar = () => {
  sidebarOpen.value = false
}

async function logout() {
  try {
    await api.logout()
  } catch {
    /* ignore */
  }
  clearSession()
  sessionUser.value = null
  await router.replace({ name: 'login' })
}

onMounted(async () => {
  await checkHealth()
  if (apiOnline.value) {
    await loadWorkspace().catch(() => {})
    try {
      const me = await api.me()
      sessionUser.value = { username: me.username, role: me.role }
    } catch {
      sessionUser.value = readSessionUser()
    }
  }
})
</script>

<template>
  <div class="shell" :class="{ 'sidebar-open': sidebarOpen }">
    <div v-if="sidebarOpen" class="overlay" @click="closeSidebar" />

    <Sidebar
      :items="sidebarItems"
      :active="currentTable"
      :loading="loading"
      :online="apiOnline"
      :user="sessionUser"
      @navigate="closeSidebar"
      @logout="logout"
    />

    <div class="main">
      <header class="topbar">
        <button type="button" class="menu-btn btn btn-ghost" aria-label="Menu" @click="sidebarOpen = !sidebarOpen">
          Menu
        </button>
        <div class="topbar-title">
          <p class="eyebrow">Diomika Backoffice</p>
          <h1>{{ pageTitle }}</h1>
        </div>
        <span class="status-chip" :class="{ online: apiOnline, offline: apiOnline === false }">
          <span class="dot" />
          {{ apiOnline ? 'API ligada' : apiOnline === false ? 'API offline' : 'A verificar…' }}
        </span>
      </header>

      <div v-if="error || apiOnline === false" class="banner error">
        <p>{{ apiOnline === false ? mapApiError('fetch failed') : mapApiError(error) }}</p>
        <button type="button" class="btn btn-ghost btn-sm" @click="retryAll">Tentar novamente</button>
      </div>

      <main class="content">
        <RouterView :key="route.fullPath" />
      </main>
    </div>
  </div>
</template>

<style scoped>
.shell {
  display: grid;
  grid-template-columns: var(--sidebar-w) 1fr;
  min-height: 100vh;
  background: var(--bg);
}

.main {
  display: flex;
  flex-direction: column;
  min-width: 0;
}

.topbar {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 1rem;
  padding: 1.1rem 1.5rem;
  border-bottom: 1px solid var(--border);
  background: rgba(255, 255, 255, 0.88);
  backdrop-filter: blur(8px);
  position: sticky;
  top: 0;
  z-index: 20;
}

.menu-btn {
  display: none;
}

.topbar-title h1 {
  margin: 0.15rem 0 0;
  font-family: var(--font-display);
  font-size: 1.55rem;
  font-weight: 560;
  letter-spacing: -0.02em;
}

.eyebrow {
  margin: 0;
  font-size: 0.7rem;
  text-transform: uppercase;
  letter-spacing: 0.08em;
  color: var(--text-muted);
  font-weight: 600;
}

.status-chip {
  display: inline-flex;
  align-items: center;
  gap: 0.4rem;
  padding: 0.35rem 0.7rem;
  border-radius: 999px;
  font-size: 0.76rem;
  font-weight: 650;
  background: var(--bg-soft);
  color: var(--text-muted);
  border: 1px solid var(--border);
  white-space: nowrap;
}

.status-chip .dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background: #98a5b3;
}

.status-chip.online {
  color: var(--success);
  border-color: rgba(31, 122, 77, 0.25);
  background: var(--success-soft);
}

.status-chip.online .dot { background: var(--success); }

.status-chip.offline {
  color: var(--danger);
  border-color: rgba(180, 35, 24, 0.25);
  background: var(--danger-soft);
}

.status-chip.offline .dot { background: var(--danger); }

.content {
  padding: 1.35rem 1.5rem 2.5rem;
  flex: 1;
}

.banner.error {
  margin: 0;
  padding: 0.8rem 1.5rem;
  background: var(--danger-soft);
  border-bottom: 1px solid rgba(180, 35, 24, 0.2);
  color: var(--danger);
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 1rem;
  flex-wrap: wrap;
}

.banner.error p {
  margin: 0;
  font-size: 0.9rem;
  font-weight: 500;
}

.overlay { display: none; }

@media (max-width: 900px) {
  .shell { grid-template-columns: 1fr; }

  .menu-btn { display: inline-flex; }

  .topbar-title h1 { font-size: 1.25rem; }

  .status-chip { display: none; }

  .overlay {
    display: block;
    position: fixed;
    inset: 0;
    background: rgba(24, 33, 43, 0.35);
    z-index: 90;
  }

  .shell :deep(.sidebar) {
    position: fixed;
    top: 0;
    left: 0;
    bottom: 0;
    z-index: 100;
    transform: translateX(-105%);
    transition: transform 0.22s ease;
    width: min(280px, 86vw);
    box-shadow: var(--shadow);
  }

  .shell.sidebar-open :deep(.sidebar) {
    transform: translateX(0);
  }

  .content { padding: 1rem; }
}
</style>
