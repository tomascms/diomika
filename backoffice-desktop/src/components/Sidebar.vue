<script setup>
import { computed } from 'vue'
import { RouterLink } from 'vue-router'

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
        {{ item.label }}
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
  background: var(--bg-panel);
  border-right: 1px solid var(--border);
  padding: 1.1rem 0.85rem;
  display: flex;
  flex-direction: column;
  gap: 1rem;
  min-height: 100vh;
}

.brand {
  display: flex;
  align-items: center;
  gap: 0.7rem;
  padding: 0.25rem 0.55rem 0.9rem;
  border-bottom: 1px solid var(--border);
}

.logo {
  width: 36px;
  height: 36px;
  border-radius: 10px;
  display: grid;
  place-items: center;
  background: var(--accent);
  color: #fff;
  font-family: var(--font-display);
  font-weight: 560;
  font-size: 1.15rem;
}

.brand strong {
  display: block;
  font-family: var(--font-display);
  font-size: 1.15rem;
  font-weight: 560;
  letter-spacing: -0.01em;
}

.brand small {
  display: block;
  color: var(--text-muted);
  font-size: 0.72rem;
  margin-top: 0.1rem;
}

.nav {
  display: flex;
  flex-direction: column;
  gap: 0.2rem;
  flex: 1;
  min-height: 0;
  overflow-y: auto;
}

.nav-status {
  margin: 0;
  padding: 0.6rem 0.7rem;
  font-size: 0.82rem;
  color: var(--text-muted);
}

.nav-item {
  display: block;
  padding: 0.62rem 0.75rem;
  border-radius: var(--radius-sm);
  color: var(--text-muted);
  text-decoration: none;
  font-weight: 550;
  font-size: 0.92rem;
  border: 1px solid transparent;
  transition: background 0.15s, color 0.15s, border-color 0.15s;
}

.nav-item:hover {
  background: var(--bg-soft);
  color: var(--text);
}

.nav-item.active {
  background: var(--accent-soft);
  color: var(--accent-hover);
  border-color: rgba(15, 110, 86, 0.18);
}

.sidebar-footer {
  border-top: 1px solid var(--border);
  padding-top: 0.75rem;
  margin-top: auto;
  display: grid;
  gap: 0.55rem;
}

.footer-link {
  margin: 0;
}

.user-box {
  padding: 0.55rem 0.65rem;
  border-radius: var(--radius-sm);
  background: var(--bg-soft);
}

.user-line {
  margin: 0;
  font-size: 0.8rem;
  color: var(--text-muted);
  display: flex;
  justify-content: space-between;
  gap: 0.5rem;
  align-items: center;
}

.user-line .role {
  text-transform: uppercase;
  letter-spacing: 0.04em;
  font-size: 0.68rem;
  font-weight: 700;
  color: var(--accent-hover);
}

.logout-btn {
  margin-top: 0.45rem;
  width: 100%;
  text-align: left;
  cursor: pointer;
  background: transparent;
  border: 0;
  padding: 0.2rem 0;
  font: inherit;
  font-size: 0.8rem;
  font-weight: 600;
  color: var(--text);
}

.logout-btn:hover {
  color: var(--danger);
}

.hint {
  margin: 0;
  padding: 0 0.35rem;
  font-size: 0.72rem;
  color: var(--text-muted);
  display: flex;
  align-items: center;
  gap: 0.4rem;
}

.status-dot {
  width: 7px;
  height: 7px;
  border-radius: 50%;
  background: #98a5b3;
  flex-shrink: 0;
}

.status-dot.online { background: var(--success); }
.status-dot.offline { background: var(--danger); }
</style>
