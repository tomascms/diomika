<script setup>
import { computed, onMounted, ref } from 'vue'
import { useRoute, useRouter, RouterView } from 'vue-router'
import { useWorkspace } from '@/composables/useWorkspace'
import { mapApiError, clearSession, readSessionUser, writeSessionUser } from '@/lib/settings'
import { api, clearApiCaches } from '@/lib/api'
import Sidebar from '@/components/Sidebar.vue'

const route = useRoute()
const router = useRouter()
const { sidebarItems, loadWorkspace, workspace, error, loading } = useWorkspace()
const currentTable = computed(() => route.params.table || '')
const sidebarOpen = ref(false)
const sessionUser = ref(readSessionUser())

const pageTitle = computed(() =>
  workspace.value?.sidebar?.[currentTable.value]?.label
    || workspace.value?.tables?.[currentTable.value]?.label
    || 'Painel',
)

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
    clearApiCaches()
  }
  clearSession()
  sessionUser.value = null
  await router.replace({ name: 'login' })
}

onMounted(() => {
  void checkHealth()
  loadWorkspace().catch(() => {})
  api.me()
    .then((me) => {
      sessionUser.value = { username: me.username, role: me.role }
      writeSessionUser(sessionUser.value)
    })
    .catch(() => {
      sessionUser.value = readSessionUser()
    })
})

const viewKey = computed(() => (route.name === 'workspace' ? 'workspace' : route.fullPath))
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
        <RouterView v-slot="{ Component }">
          <KeepAlive :include="['WorkspaceRouter']" :max="4">
            <component :is="Component" :key="viewKey" />
          </KeepAlive>
        </RouterView>
      </main>
    </div>
  </div>
</template>

<style scoped>
.shell {
  display: grid;
  grid-template-columns: var(--sidebar-w) 1fr;
  grid-template-rows: var(--header-height) 1fr;
  min-height: 100vh;
  background: var(--bg);
  gap: 0;
}

.main {
  display: flex;
  flex-direction: column;
  min-width: 0;
  grid-column: 2;
  grid-row: 1 / -1;
}

.topbar {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 2rem;
  padding: 0 2rem;
  border-bottom: 1px solid var(--border);
  background: var(--surface);
  backdrop-filter: blur(12px);
  position: sticky;
  top: 0;
  z-index: 20;
  box-shadow: var(--shadow-sm);
}

.menu-btn {
  display: none;
  padding: 8px 12px;
  font-size: 14px;
  border-radius: var(--radius);
}

.topbar-title {
  flex: 1;
}

.topbar-title h1 {
  margin: 0;
  font-family: var(--font-display);
  font-size: 24px;
  font-weight: 700;
  letter-spacing: -0.01em;
  color: var(--text-primary);
}

.eyebrow {
  margin: 0 0 4px 0;
  font-size: 11px;
  text-transform: uppercase;
  letter-spacing: 0.6px;
  color: var(--text-muted);
  font-weight: 600;
}

.status-chip {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  padding: 6px 12px;
  border-radius: 999px;
  font-size: 12px;
  font-weight: 600;
  background: var(--bg-secondary);
  color: var(--text-secondary);
  border: 1px solid var(--border);
  white-space: nowrap;
  transition: all var(--transition);
}

.status-chip .dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background: var(--text-muted);
  animation: pulse 2s ease-in-out infinite;
}

@keyframes pulse {
  0%, 100% { opacity: 1; }
  50% { opacity: 0.5; }
}

.status-chip.online {
  color: var(--success);
  border-color: rgba(16, 185, 129, 0.2);
  background: var(--success-soft);
}

.status-chip.online .dot {
  background: var(--success);
}

.status-chip.offline {
  color: var(--danger);
  border-color: rgba(239, 68, 68, 0.2);
  background: var(--danger-soft);
}

.status-chip.offline .dot {
  background: var(--danger);
  animation: none;
}

.content {
  padding: 24px;
  flex: 1;
  overflow-y: auto;
  overflow-x: hidden;
  -webkit-overflow-scrolling: touch;
}

.banner.error {
  margin: 0 0 16px 0;
  padding: 12px 16px;
  background: var(--danger-soft);
  border: 1px solid rgba(239, 68, 68, 0.2);
  border-radius: var(--radius);
  color: var(--danger);
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
  flex-wrap: wrap;
}

.banner.error p {
  margin: 0;
  font-size: 14px;
  font-weight: 500;
}

.overlay {
  display: none;
}

@media (max-width: 900px) {
  .shell {
    grid-template-columns: 1fr;
  }

  .main {
    grid-column: 1;
  }

  .menu-btn {
    display: inline-flex;
  }

  .topbar {
    gap: 1rem;
    padding: 0 1rem;
  }

  .topbar-title h1 {
    font-size: 18px;
  }

  .status-chip {
    display: none;
  }

  .overlay {
    display: block;
    position: fixed;
    inset: 0;
    background: rgba(15, 23, 42, 0.5);
    z-index: 90;
    backdrop-filter: blur(4px);
  }

  .shell :deep(.sidebar) {
    position: fixed;
    top: 0;
    left: 0;
    bottom: 0;
    z-index: 100;
    transform: translateX(-105%);
    transition: transform var(--transition) cubic-bezier(0.4, 0, 0.2, 1);
    width: min(280px, 86vw);
    box-shadow: var(--shadow-lg);
  }

  .shell.sidebar-open :deep(.sidebar) {
    transform: translateX(0);
  }

  .content {
    padding: 16px;
  }
}
</style>
