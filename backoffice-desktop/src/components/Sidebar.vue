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
  background: linear-gradient(180deg, var(--surface) 0%, rgba(59, 130, 246, 0.02) 100%);
  border-right: 1px solid var(--border);
  padding: 16px 12px;
  display: flex;
  flex-direction: column;
  gap: 16px;
  min-height: 100vh;
  overflow-y: auto;
  transition: all var(--transition);
}

.brand {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 14px 12px;
  border-bottom: 2px solid var(--border);
  margin-bottom: 12px;
  background: linear-gradient(135deg, rgba(59, 130, 246, 0.05) 0%, transparent 100%);
  border-radius: var(--radius-sm);
  transition: all var(--transition);
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
  border-radius: var(--radius-md);
  color: var(--text-secondary);
  text-decoration: none;
  font-weight: 500;
  font-size: 14px;
  border: 1px solid transparent;
  transition: all var(--transition);
  position: relative;
  overflow: hidden;
}

.nav-item::before {
  content: '';
  position: absolute;
  left: 0;
  top: 0;
  bottom: 0;
  width: 3px;
  background: var(--accent);
  transform: scaleY(0);
  transform-origin: center;
  transition: transform var(--transition);
  pointer-events: none;
}

.nav-item .app-icon {
  opacity: 0.6;
  transition: opacity var(--transition);
  z-index: 1;
}

.nav-item.active .app-icon,
.nav-item:hover .app-icon {
  opacity: 1;
}

.nav-item:hover {
  background: linear-gradient(135deg, rgba(59, 130, 246, 0.08) 0%, rgba(59, 130, 246, 0.02) 100%);
  color: var(--accent);
  transform: translateX(2px);
}

.nav-item.active {
  background: linear-gradient(135deg, rgba(59, 130, 246, 0.15) 0%, rgba(30, 64, 175, 0.1) 100%);
  color: var(--accent);
  border-color: rgba(59, 130, 246, 0.3);
  font-weight: 700;
  box-shadow: 0 2px 8px rgba(59, 130, 246, 0.15);
}

.nav-item.active::before {
  transform: scaleY(1);
}

.sidebar-footer {
  border-top: 1px solid var(--border);
  padding-top: 12px;
  margin-top: auto;
  display: grid;
  gap: 8px;
}

.user-box {
  padding: 12px;
  border-radius: var(--radius-md);
  background: linear-gradient(135deg, rgba(59, 130, 246, 0.08) 0%, rgba(59, 130, 246, 0.02) 100%);
  border: 1px solid rgba(59, 130, 246, 0.15);
  transition: all var(--transition);
}

.user-box:hover {
  border-color: rgba(59, 130, 246, 0.3);
  box-shadow: 0 2px 8px rgba(59, 130, 246, 0.1);
}

.user-line {
  margin: 0;
  font-size: 12px;
  color: var(--text-secondary);
  display: flex;
  justify-content: space-between;
  gap: 8px;
  align-items: center;
  font-weight: 500;
}

.user-line .role {
  text-transform: uppercase;
  letter-spacing: 0.6px;
  font-size: 9px;
  font-weight: 700;
  color: var(--accent);
  padding: 2px 6px;
  background: rgba(59, 130, 246, 0.1);
  border-radius: 3px;
}

.logout-btn {
  margin-top: 8px;
  width: 100%;
  text-align: left;
  cursor: pointer;
  background: transparent;
  border: none;
  padding: 6px 0;
  font: inherit;
  font-size: 11px;
  font-weight: 700;
  letter-spacing: 0.3px;
  color: var(--text-secondary);
  transition: all var(--transition);
  text-transform: uppercase;
}

.logout-btn:hover {
  color: var(--danger);
  transform: translateX(2px);
}

.sidebar-footer {
  border-top: 2px solid var(--border);
  padding-top: 12px;
  margin-top: auto;
  display: grid;
  gap: 10px;
}

.hint {
  margin: 0;
  padding: 0 8px;
  font-size: 10px;
  font-weight: 600;
  letter-spacing: 0.3px;
  color: var(--text-muted);
  display: flex;
  align-items: center;
  gap: 6px;
  text-transform: uppercase;
}

.status-dot {
  width: 6px;
  height: 6px;
  border-radius: 50%;
  background: var(--text-muted);
  flex-shrink: 0;
  animation: pulse 2s ease-in-out infinite;
}

.status-dot.online {
  background: var(--success);
  box-shadow: 0 0 0 2px rgba(16, 185, 129, 0.2);
}

.status-dot.offline {
  background: var(--danger);
  box-shadow: 0 0 0 2px rgba(239, 68, 68, 0.2);
  animation: pulse-danger 1s ease-in-out infinite;
}

@keyframes pulse-danger {
  0%, 100% { opacity: 1; }
  50% { opacity: 0.6; }
}
</style>
