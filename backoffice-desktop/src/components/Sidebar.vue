<script setup>
import { computed } from 'vue'
import { RouterLink } from 'vue-router'
import AppIcon from '@/components/AppIcon.vue'

const props = defineProps({
  items: { type: Array, default: () => [] },
  active: { type: String, default: '' },
  loading: { type: Boolean, default: false },
  online: { type: Boolean, default: null },
  user: { type: Object, default: null },
})

defineEmits(['navigate', 'logout'])

const displayName = computed(() => {
  const name = props.user?.username || ''
  if (!name || name === 'api-key') return 'Sessão local'
  return name
})
</script>

<template>
  <aside class="sidebar">
    <div class="brand">
      <span class="logo" aria-hidden="true">D</span>
      <div>
        <strong>Diomika</strong>
        <small>Backoffice</small>
      </div>
    </div>

    <nav class="nav" aria-label="Secções">
      <p v-if="loading" class="nav-status">A carregar…</p>
      <RouterLink
        v-for="item in items"
        :key="item.key"
        :to="`/workspace/${item.key}`"
        class="nav-item"
        :class="{ active: active === item.key }"
        @click="$emit('navigate')"
      >
        <AppIcon :name="item.icon || 'folder'" :size="17" />
        <span>{{ item.label }}</span>
      </RouterLink>
    </nav>

    <div class="sidebar-footer">
      <div v-if="user" class="user-box">
        <p class="user-line">
          <span>{{ displayName }}</span>
          <span class="role">{{ user.role }}</span>
        </p>
        <button type="button" class="logout-btn" @click="$emit('logout')">
          Terminar sessão
        </button>
      </div>

      <p class="hint">
        <span class="status-dot" :class="{ online, offline: online === false }" />
        {{ online ? 'API local ligada' : online === false ? 'API offline' : 'A verificar API…' }}
      </p>
    </div>
  </aside>
</template>

<style scoped>
.sidebar {
  width: var(--sidebar-w);
  background: var(--surface);
  border-right: 1px solid var(--border);
  padding: 16px 12px;
  display: flex;
  flex-direction: column;
  gap: 16px;
  min-height: 100vh;
  overflow-y: auto;
}

.brand {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 12px;
  border-bottom: 1px solid var(--border);
  margin-bottom: 8px;
}

.logo {
  width: 40px;
  height: 40px;
  border-radius: var(--radius);
  display: grid;
  place-items: center;
  background: linear-gradient(135deg, var(--accent) 0%, var(--accent-dark) 100%);
  color: white;
  font-family: var(--font-display);
  font-weight: 700;
  font-size: 18px;
  box-shadow: var(--shadow-sm);
}

.brand strong {
  display: block;
  font-family: var(--font-display);
  font-size: 16px;
  font-weight: 700;
  letter-spacing: -0.01em;
  color: var(--text-primary);
}

.brand small {
  display: block;
  color: var(--text-muted);
  font-size: 11px;
  margin-top: 2px;
  font-weight: 500;
}

.nav {
  display: flex;
  flex-direction: column;
  gap: 4px;
  flex: 1;
  min-height: 0;
  overflow-y: auto;
}

.nav-status {
  margin: 0;
  padding: 8px 12px;
  font-size: 12px;
  color: var(--text-muted);
}

.nav-item {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 10px 12px;
  border-radius: var(--radius);
  color: var(--text-secondary);
  text-decoration: none;
  font-weight: 500;
  font-size: 14px;
  border: 1px solid transparent;
  transition: all var(--transition);
}

.nav-item .app-icon {
  opacity: 0.6;
  transition: opacity var(--transition);
}

.nav-item.active .app-icon,
.nav-item:hover .app-icon {
  opacity: 1;
}

.nav-item:hover {
  background: var(--bg-secondary);
  color: var(--text-primary);
}

.nav-item.active {
  background: linear-gradient(135deg, rgba(59, 130, 246, 0.15) 0%, rgba(30, 64, 175, 0.1) 100%);
  color: var(--accent);
  border-color: rgba(59, 130, 246, 0.2);
  font-weight: 600;
}

.sidebar-footer {
  border-top: 1px solid var(--border);
  padding-top: 12px;
  margin-top: auto;
  display: grid;
  gap: 8px;
}

.user-box {
  padding: 10px 12px;
  border-radius: var(--radius);
  background: var(--bg-secondary);
  border: 1px solid var(--border);
}

.user-line {
  margin: 0;
  font-size: 12px;
  color: var(--text-secondary);
  display: flex;
  justify-content: space-between;
  gap: 8px;
  align-items: center;
}

.user-line .role {
  text-transform: uppercase;
  letter-spacing: 0.5px;
  font-size: 10px;
  font-weight: 700;
  color: var(--accent);
}

.logout-btn {
  margin-top: 6px;
  width: 100%;
  text-align: left;
  cursor: pointer;
  background: transparent;
  border: none;
  padding: 4px 0;
  font: inherit;
  font-size: 12px;
  font-weight: 600;
  color: var(--text-secondary);
  transition: color var(--transition);
}

.logout-btn:hover {
  color: var(--danger);
}

.hint {
  margin: 0;
  padding: 0 8px;
  font-size: 11px;
  color: var(--text-muted);
  display: flex;
  align-items: center;
  gap: 6px;
}

.status-dot {
  width: 6px;
  height: 6px;
  border-radius: 50%;
  background: var(--text-muted);
  flex-shrink: 0;
}

.status-dot.online {
  background: var(--success);
}

.status-dot.offline {
  background: var(--danger);
}
</style>
