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
  background: linear-gradient(180deg, var(--surface) 0%, rgba(59, 130, 246, 0.02) 100%);
  backdrop-filter: blur(12px);
  position: sticky;
  top: 0;
  z-index: 20;
  box-shadow: var(--shadow-sm);
  transition: all var(--transition);
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
  padding: 7px 14px;
  border-radius: 999px;
  font-size: 11px;
  font-weight: 700;
  letter-spacing: 0.3px;
  text-transform: uppercase;
  background: var(--bg-secondary);
  color: var(--text-secondary);
  border: 1px solid var(--border);
  white-space: nowrap;
  transition: all var(--transition);
  box-shadow: 0 2px 8px rgba(15, 23, 42, 0.06);
}

.status-chip .dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background: var(--text-muted);
  animation: pulse 2s ease-in-out infinite;
  box-shadow: 0 0 0 2px rgba(15, 23, 42, 0.08);
}

@keyframes pulse {
  0%, 100% { opacity: 1; }
  50% { opacity: 0.5; }
}

.status-chip.online {
  color: var(--success);
  border-color: rgba(16, 185, 129, 0.3);
  background: linear-gradient(135deg, rgba(16, 185, 129, 0.12) 0%, rgba(16, 185, 129, 0.04) 100%);
  box-shadow: 0 2px 8px rgba(16, 185, 129, 0.15);
}

.status-chip.online .dot {
  background: var(--success);
  box-shadow: 0 0 0 2px rgba(16, 185, 129, 0.2);
}

.status-chip.offline {
  color: var(--danger);
  border-color: rgba(239, 68, 68, 0.3);
  background: linear-gradient(135deg, rgba(239, 68, 68, 0.12) 0%, rgba(239, 68, 68, 0.04) 100%);
  box-shadow: 0 2px 8px rgba(239, 68, 68, 0.15);
  animation: pulse-danger 1s ease-in-out infinite;
}

.status-chip.offline .dot {
  background: var(--danger);
  box-shadow: 0 0 0 2px rgba(239, 68, 68, 0.2);
  animation: pulse-danger 1s ease-in-out infinite;
}

@keyframes pulse-danger {
  0%, 100% { opacity: 1; }
  50% { opacity: 0.7; }
}

.content {
  padding: 24px;
  flex: 1;
  overflow-y: auto;
}

.banner.error {
  margin: 0 0 16px 0;
  padding: 14px 16px;
  background: linear-gradient(135deg, rgba(239, 68, 68, 0.12) 0%, rgba(239, 68, 68, 0.04) 100%);
  border: 1px solid rgba(239, 68, 68, 0.3);
  border-left: 4px solid var(--danger);
  border-radius: var(--radius-md);
  color: var(--danger);
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
  flex-wrap: wrap;
  animation: slideDown 0.3s ease-out;
  box-shadow: 0 2px 8px rgba(239, 68, 68, 0.12);
}

.banner.error p {
  margin: 0;
  font-size: 14px;
  font-weight: 500;
  line-height: 1.4;
}

@keyframes slideDown {
  from {
    opacity: 0;
    transform: translateY(-8px);
  }
  to {
    opacity: 1;
    transform: translateY(0);
  }
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
